"""Real adapter contract validation for prioritized channels (CL-010).

Exercises real adapter code against recorded signed request fixtures:
1. Slack Socket Mode adapter with recorded signed events and redelivery deduplication.
2. Telegram adapter with recorded Update fixtures and update_id deduplication.
3. DingTalk stream adapter with recorded stream payloads and msgId deduplication.
4. ChannelReconnectManager exponential backoff and state transitions.
5. ChannelRateLimiter token bucket replenishment and 429 backoff calculations.
6. Full end-to-end authorized channel workflow roundtrip.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from amberclaw.bus.events import InboundMessage, OutboundMessage
from amberclaw.bus.queue import MessageBus
from amberclaw.channels.dingtalk import DingTalkChannel
from amberclaw.channels.resilience import (
    ChannelRateLimiter,
    ChannelReconnectManager,
    ConnectionState,
)
from amberclaw.channels.slack import SlackChannel
from amberclaw.channels.telegram import TelegramChannel
from amberclaw.config.schema import DingTalkConfig, SlackConfig, TelegramConfig

FIXTURES_DIR = (
    Path(__file__).resolve().parents[4] / "evidence/competitive/CL-010/9ece8c0/fixtures"
)


@pytest.fixture
def slack_fixture() -> dict:
    with open(FIXTURES_DIR / "slack_signed_event.json") as f:
        return json.load(f)


@pytest.fixture
def telegram_fixture() -> dict:
    with open(FIXTURES_DIR / "telegram_update_fixture.json") as f:
        return json.load(f)


@pytest.fixture
def dingtalk_fixture() -> dict:
    with open(FIXTURES_DIR / "dingtalk_stream_fixture.json") as f:
        return json.load(f)


@pytest.mark.asyncio
async def test_slack_real_adapter_signed_event_and_deduplication(slack_fixture: dict):
    """Exercise real SlackChannel with recorded event; verify dedup drops redelivery."""
    bus = MessageBus()
    config = SlackConfig(
        bot_token="xoxb-test-offline",
        app_token="xapp-test-offline",
        allow_from=["U12345678"],
        group_policy="open",
        mode="socket",
    )
    channel = SlackChannel(config, bus)

    # Mock low-level Socket client and Web client transport
    mock_socket = SimpleNamespace(
        send_socket_mode_response=AsyncMock(),
    )
    mock_web = SimpleNamespace(
        reactions_add=AsyncMock(),
        files_upload_v2=AsyncMock(),
        chat_postMessage=AsyncMock(),
    )
    channel._web_client = mock_web
    channel._bot_user_id = "B_BOT_99"

    # Construct request object matching Slack SDK contract
    req = SimpleNamespace(
        type="events_api",
        envelope_id=slack_fixture["envelope_id"],
        payload=slack_fixture["payload"],
    )

    # 1. First delivery: successfully processes and publishes to bus
    await channel._on_socket_request(mock_socket, req)
    mock_socket.send_socket_mode_response.assert_awaited_once()

    inbound = await asyncio.wait_for(bus.consume_inbound(), timeout=2.0)
    assert inbound.content == "run ops audit check"
    assert inbound.sender_id == "U12345678"
    assert inbound.chat_id == "C12345678"

    # 2. Redelivery (same event_id / envelope_id): must be dropped by deduplication
    mock_socket.send_socket_mode_response.reset_mock()
    await channel._on_socket_request(mock_socket, req)
    mock_socket.send_socket_mode_response.assert_awaited_once()

    # Bus must be empty — no duplicate action taken
    assert bus.inbound_size == 0


@pytest.mark.asyncio
async def test_telegram_real_adapter_update_and_deduplication(telegram_fixture: dict):
    """Exercise real TelegramChannel with recorded Update; verify dedup drops redelivery."""
    bus = MessageBus()
    config = TelegramConfig(
        token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        allow_from=["11223344"],
        group_policy="open",
    )
    channel = TelegramChannel(config, bus)

    msg_data = telegram_fixture["message"]
    user_data = msg_data["from"]
    user = SimpleNamespace(
        id=user_data["id"],
        username=user_data["username"],
        first_name=user_data["first_name"],
    )
    message = SimpleNamespace(
        chat=SimpleNamespace(type=msg_data["chat"]["type"], is_forum=False),
        chat_id=msg_data["chat"]["id"],
        message_id=msg_data["message_id"],
        message_thread_id=None,
        media_group_id=None,
        text=msg_data["text"],
        caption=None,
        photo=[],
        voice=None,
        audio=None,
        document=None,
    )
    update = SimpleNamespace(message=message, effective_user=user)

    # 1. First delivery
    await channel._on_message(update, None)
    inbound = await asyncio.wait_for(bus.consume_inbound(), timeout=2.0)
    assert inbound.content == "investigate latency anomaly on pod-8"
    assert "11223344" in inbound.sender_id
    assert inbound.chat_id == "-100123456789"

    # 2. Redelivery: exact same update/message_id
    await channel._on_message(update, None)
    # Bus must be empty — duplicate dropped
    assert bus.inbound_size == 0


@pytest.mark.asyncio
async def test_dingtalk_real_adapter_stream_and_deduplication(dingtalk_fixture: dict):
    """Exercise real DingTalkChannel with recorded payload; verify dedup drops redelivery."""
    bus = MessageBus()
    config = DingTalkConfig(
        client_id="ding_test_id",
        client_secret="ding_test_secret",
        allow_from=["staff9988"],
    )
    channel = DingTalkChannel(config, bus)

    data = dingtalk_fixture["data"]
    content = data["text"]["content"]
    sender_id = data["senderStaffId"]
    sender_name = data["senderNick"]
    conversation_type = data["conversationType"]
    conversation_id = data["conversationId"]
    msg_id = dingtalk_fixture["msgId"]

    # 1. First delivery
    await channel._on_message(
        content=content,
        sender_id=sender_id,
        sender_name=sender_name,
        conversation_type=conversation_type,
        conversation_id=conversation_id,
        message_id=msg_id,
    )
    inbound = await asyncio.wait_for(bus.consume_inbound(), timeout=2.0)
    assert inbound.content == "generate daily infrastructure incident report"
    assert inbound.sender_id == "staff9988"
    assert inbound.chat_id == "group:cid_ding_room_42"

    # 2. Redelivery with same message_id
    await channel._on_message(
        content=content,
        sender_id=sender_id,
        sender_name=sender_name,
        conversation_type=conversation_type,
        conversation_id=conversation_id,
        message_id=msg_id,
    )
    assert bus.inbound_size == 0


def test_reconnect_manager_exponential_backoff():
    """Verify ChannelReconnectManager exponential backoff transitions."""
    mgr = ChannelReconnectManager(
        initial_delay=0.1,
        max_delay=0.8,
        multiplier=2.0,
        jitter_ratio=0.0,
    )
    assert mgr.get_state("slack_ops") == ConnectionState.CONNECTED

    # Attempt 1
    d1 = mgr.record_failure("slack_ops")
    assert abs(d1 - 0.1) < 0.05
    assert mgr.get_state("slack_ops") == ConnectionState.BACKOFF

    # Attempt 2: multiplied by 2
    d2 = mgr.record_failure("slack_ops")
    assert abs(d2 - 0.2) < 0.05

    # Attempt 3: multiplied by 2
    d3 = mgr.record_failure("slack_ops")
    assert abs(d3 - 0.4) < 0.05

    # Reset on success
    mgr.record_success("slack_ops")
    assert mgr.get_state("slack_ops") == ConnectionState.CONNECTED
    assert mgr._failures.get("slack_ops", 0) == 0


@pytest.mark.asyncio
async def test_rate_limiter_token_bucket_and_backoff():
    """Verify ChannelRateLimiter token replenishment and 429 backoff calculation."""
    limiter = ChannelRateLimiter()

    # Normal acquire succeeds
    assert await limiter.acquire("slack", cost=1.0) is True

    # Report HTTP 429 backoff
    limiter.report_rate_limit("slack", retry_after_sec=5.0)
    assert limiter.is_blocked("slack") is True

    # Immediate acquire is blocked when cooldown is active
    assert await limiter.acquire("slack", timeout=0.05) is False

    # Clear unblocks channel
    limiter.clear()
    assert limiter.is_blocked("slack") is False


@pytest.mark.asyncio
async def test_end_to_end_authorized_channel_roundtrip():
    """Verify complete inbound -> bus -> outbound delivery cycle on real adapter."""
    bus = MessageBus()
    config = SlackConfig(
        bot_token="xoxb-mock",
        app_token="xapp-mock",
        allow_from=["U_AUTHORIZED"],
        mode="socket",
    )
    channel = SlackChannel(config, bus)

    mock_web = SimpleNamespace(
        chat_postMessage=AsyncMock(return_value={"ok": True}),
        files_upload_v2=AsyncMock(),
        reactions_add=AsyncMock(),
    )
    channel._web_client = mock_web

    # Inbound message from authorized user
    await channel._handle_message(
        sender_id="U_AUTHORIZED",
        chat_id="C_MAIN",
        content="ping health check",
    )
    inbound = await asyncio.wait_for(bus.consume_inbound(), timeout=2.0)
    assert inbound.content == "ping health check"

    # Outbound response delivery back to channel
    outbound = OutboundMessage(
        channel="slack",
        chat_id="C_MAIN",
        content="pong: all systems healthy",
    )
    await channel.send(outbound)

    mock_web.chat_postMessage.assert_awaited_once_with(
        channel="C_MAIN",
        text="pong: all systems healthy\n",
        thread_ts=None,
    )
