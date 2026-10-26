# ruff: noqa: PLR2004, PLC0415
"""Integration tests for AmberClaw Live Messaging Channels and Resilience Engine.

Validates:
1. BaseChannel inbound message filtering, permission gating, and bus dispatch
2. Pairing bypass (/pair) for unauthenticated senders
3. ChannelManager outbound routing and multi-channel dispatch
4. ChannelRateLimiter token replenishment and HTTP 429 Retry-After backoff
5. ChannelReconnectManager exponential backoff state transitions
6. ChannelMetricsTracker latency percentiles and throughput accounting
7. CrossChannelContinuityManager identity mapping and cross-channel session handoff
"""

import asyncio
from types import SimpleNamespace

import pytest

from amberclaw.bus.events import InboundMessage, OutboundMessage
from amberclaw.bus.queue import MessageBus
from amberclaw.channels.base import BaseChannel
from amberclaw.channels.continuity import CrossChannelContinuityManager
from amberclaw.channels.manager import ChannelManager
from amberclaw.channels.resilience import (
    ChannelMetricsTracker,
    ChannelRateLimiter,
    ChannelReconnectManager,
    ConnectionState,
)


class MockLiveChannel(BaseChannel):
    """Concrete channel implementation for live integration testing."""

    name = "mock_channel"

    def __init__(self, config, bus: MessageBus):
        super().__init__(config, bus)
        self.sent_messages: list[OutboundMessage] = []
        self._running = False

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        self.sent_messages.append(msg)


@pytest.mark.asyncio
async def test_base_channel_permission_gating_and_bus_delivery():
    bus = MessageBus()
    inbound_delivered: list[InboundMessage] = []

    async def capture_inbound(msg: InboundMessage):
        inbound_delivered.append(msg)

    bus.publish_inbound = capture_inbound

    # Channel 1: specific allowlist
    cfg = SimpleNamespace(allow_from=["alice_123", "bob_456"])
    channel = MockLiveChannel(cfg, bus)

    # Allowed sender
    await channel._handle_message(
        sender_id="alice_123",
        chat_id="chat_001",
        content="Hello Agent",
    )
    assert len(inbound_delivered) == 1
    assert inbound_delivered[0].sender_id == "alice_123"
    assert inbound_delivered[0].content == "Hello Agent"

    # Unauthorized sender - blocked
    await channel._handle_message(
        sender_id="mallory_evil",
        chat_id="chat_001",
        content="Unauthorized instruction",
    )
    assert len(inbound_delivered) == 1  # No additional message delivered

    # Pairing command bypass for unauthorized sender
    await channel._handle_message(
        sender_id="mallory_evil",
        chat_id="chat_001",
        content="/pair 987654",
    )
    assert len(inbound_delivered) == 2
    assert inbound_delivered[1].content == "/pair 987654"


@pytest.mark.asyncio
async def test_base_channel_wildcard_permission():
    bus = MessageBus()
    inbound_delivered: list[InboundMessage] = []
    bus.publish_inbound = lambda msg: inbound_delivered.append(msg) or asyncio.sleep(0)

    cfg = SimpleNamespace(allow_from=["*"])
    channel = MockLiveChannel(cfg, bus)

    await channel._handle_message(
        sender_id="anyone_anywhere",
        chat_id="global_room",
        content="Public broadcast query",
    )
    assert len(inbound_delivered) == 1
    assert inbound_delivered[0].sender_id == "anyone_anywhere"


@pytest.mark.asyncio
async def test_channel_manager_outbound_routing():
    bus = MessageBus()
    from amberclaw.config.schema import Config

    cfg = Config()
    mgr = ChannelManager(cfg, bus)

    mock_telegram = MockLiveChannel(SimpleNamespace(allow_from=["*"]), bus)
    mock_discord = MockLiveChannel(SimpleNamespace(allow_from=["*"]), bus)

    mgr.channels["telegram"] = mock_telegram
    mgr.channels["discord"] = mock_discord

    # Start outbound dispatcher background task
    dispatch_task = asyncio.create_task(mgr._dispatch_outbound())

    try:
        # Dispatch to telegram
        out_tg = OutboundMessage(
            channel="telegram", chat_id="tg_group_1", content="Alert: build passed"
        )
        await bus.publish_outbound(out_tg)

        # Dispatch to discord
        out_dc = OutboundMessage(
            channel="discord", chat_id="dc_chan_2", content="Daily standup reminder"
        )
        await bus.publish_outbound(out_dc)

        # Allow dispatcher task to consume messages
        await asyncio.sleep(0.05)

        # Verify routing isolation
        assert len(mock_telegram.sent_messages) == 1
        assert mock_telegram.sent_messages[0].content == "Alert: build passed"
        assert len(mock_discord.sent_messages) == 1
        assert mock_discord.sent_messages[0].content == "Daily standup reminder"
    finally:
        dispatch_task.cancel()
        await dispatch_task


@pytest.mark.asyncio
async def test_channel_rate_limiter_and_retry_after():
    limiter = ChannelRateLimiter()

    # Normal acquisition should succeed
    acquired = await limiter.acquire("telegram", cost=1.0, timeout=1.0)
    assert acquired is True

    # Block channel due to HTTP 429
    limiter.report_rate_limit("telegram", retry_after_sec=0.2)
    assert limiter.is_blocked("telegram") is True

    # Immediate acquire with short timeout should fail while blocked
    blocked = await limiter.acquire("telegram", cost=1.0, timeout=0.05)
    assert blocked is False

    # Wait for Retry-After to expire
    await asyncio.sleep(0.25)
    assert limiter.is_blocked("telegram") is False

    # Should succeed again
    recovered = await limiter.acquire("telegram", cost=1.0, timeout=1.0)
    assert recovered is True


def test_channel_reconnect_manager_backoff():
    manager = ChannelReconnectManager(
        initial_delay=1.0, max_delay=10.0, multiplier=2.0, jitter_ratio=0.0
    )

    # Failure 1: delay ~ 1.0s
    delay1 = manager.record_failure("discord")
    assert 0.9 <= delay1 <= 1.1
    assert manager.get_state("discord") == ConnectionState.BACKOFF

    # Failure 2: delay ~ 2.0s
    delay2 = manager.record_failure("discord")
    assert 1.9 <= delay2 <= 2.1

    # Failure 3: delay ~ 4.0s
    delay3 = manager.record_failure("discord")
    assert 3.9 <= delay3 <= 4.1

    # Check retry threshold
    assert manager.should_retry("discord", max_retries=5) is True

    # Reach max retries
    manager.record_failure("discord")
    manager.record_failure("discord")
    assert manager.should_retry("discord", max_retries=5) is False
    assert manager.get_state("discord") == ConnectionState.FAILED

    # Record success resets failures and state
    manager.record_success("discord")
    assert manager.get_state("discord") == ConnectionState.CONNECTED
    assert manager.should_retry("discord", max_retries=5) is True


def test_channel_metrics_tracker():
    tracker = ChannelMetricsTracker()

    # Inbound metrics
    tracker.record_inbound("slack")
    tracker.record_inbound("slack")

    # Delivery metrics
    tracker.record_delivery("slack", duration_ms=15.0, success=True)
    tracker.record_delivery("slack", duration_ms=25.0, success=True)
    tracker.record_delivery("slack", duration_ms=45.0, success=False)
    tracker.record_reconnect("slack")

    stats = tracker.get_stats("slack")
    assert stats["messages_received"] == 2
    assert stats["messages_sent"] == 2
    assert stats["messages_failed"] == 1
    assert stats["success_rate"] == 0.6667
    assert stats["reconnect_events"] == 1
    assert stats["latency_p50_ms"] >= 15.0


def test_cross_channel_continuity():
    continuity = CrossChannelContinuityManager()

    # Link Telegram ID and Slack ID to canonical user 'alice'
    link_tg = continuity.link_identity(
        canonical_user_id="user_alice",
        channel="telegram",
        channel_user_id="12345678",
        metadata={"handle": "@alice_tg"},
    )
    link_sl = continuity.link_identity(
        canonical_user_id="user_alice",
        channel="slack",
        channel_user_id="U99887766",
        metadata={"team": "Engineering"},
    )

    assert link_tg.canonical_user_id == "user_alice"
    assert link_sl.canonical_user_id == "user_alice"

    # Resolve canonical identity from each channel
    assert continuity.resolve_canonical_user("telegram", "12345678") == "user_alice"
    assert continuity.resolve_canonical_user("slack", "U99887766") == "user_alice"
    assert (
        continuity.resolve_canonical_user("telegram", "unknown_user")
        == "telegram_unknown_user"
    )

    # Track active session across handovers
    continuity.bind_session("user_alice", "session_shared_uuid_99")
    assert (
        continuity.get_active_session("telegram", "12345678")
        == "session_shared_uuid_99"
    )
    assert (
        continuity.get_active_session("slack", "U99887766") == "session_shared_uuid_99"
    )
