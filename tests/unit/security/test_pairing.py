"""Unit tests for the DM pairing verification code flow."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from amberclaw.agent.loop import AgentLoop
from amberclaw.bus.events import InboundMessage, OutboundMessage
from amberclaw.bus.queue import MessageBus
from amberclaw.channels.base import BaseChannel
from amberclaw.security.dm_pairing import (
    generate_pairing_code,
    get_pairing_file,
    verify_and_consume_code,
)


class _DummyChannel(BaseChannel):
    name = "dummy"

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def send(self, msg: OutboundMessage) -> None:
        pass


@pytest.fixture
def temp_pairing_dir(tmp_path):
    with patch("amberclaw.security.dm_pairing.get_data_dir", return_value=tmp_path):
        yield tmp_path


def test_generate_and_verify_code(temp_pairing_dir):
    # Generate code
    code = generate_pairing_code(expires_in_seconds=10)
    assert len(code) == 6
    assert code.isdigit()

    file_path = get_pairing_file()
    assert file_path.exists()

    # Check verification and consumption
    assert verify_and_consume_code(code) is True
    # Once consumed, it shouldn't verify again
    assert verify_and_consume_code(code) is False


def test_expired_code(temp_pairing_dir):
    code = generate_pairing_code(expires_in_seconds=-1)  # Already expired
    assert verify_and_consume_code(code) is False


def test_invalid_code(temp_pairing_dir):
    assert verify_and_consume_code("999999") is False


def test_base_channel_allows_pair_bypass():
    bus = MessageBus()
    channel = _DummyChannel(SimpleNamespace(allow_from=[]), bus)

    assert channel.is_allowed("user123") is False

    bus.publish_inbound = AsyncMock()

    # Send normal message - should be blocked
    asyncio.run(channel._handle_message("user123", "chat123", "hello"))
    bus.publish_inbound.assert_not_called()

    # Send /pair command - should bypass is_allowed and publish
    asyncio.run(channel._handle_message("user123", "chat123", "/pair"))
    bus.publish_inbound.assert_called_once()

    # Reset mock and try /pair 123456
    bus.publish_inbound.reset_mock()
    asyncio.run(channel._handle_message("user123", "chat123", "/pair 123456"))
    bus.publish_inbound.assert_called_once()


@pytest.mark.asyncio
async def test_agent_loop_handle_pairing(temp_pairing_dir, tmp_path):
    bus = MessageBus()
    bus.publish_outbound = AsyncMock()

    mock_config_path = tmp_path / "config.json"

    class FakeChannelsConfig:

        def __init__(self):
            self.dummy = SimpleNamespace(allow_from=[])

    channels_cfg = FakeChannelsConfig()

    agent = AgentLoop(
        bus=bus,
        provider=MagicMock(),
        workspace=tmp_path,
        channels_config=channels_cfg,
    )

    # 1. Request pairing instructions (no code)
    msg_inst = InboundMessage(
        channel="dummy",
        sender_id="user123",
        chat_id="chat123",
        content="/pair",
    )
    await agent._handle_pairing(msg_inst)
    bus.publish_outbound.assert_called_once()
    args, _ = bus.publish_outbound.call_args
    assert "To pair this account" in args[0].content

    # 2. Try with invalid/expired code
    bus.publish_outbound.reset_mock()
    msg_invalid = InboundMessage(
        channel="dummy",
        sender_id="user123",
        chat_id="chat123",
        content="/pair 999999",
    )
    await agent._handle_pairing(msg_invalid)
    args, _ = bus.publish_outbound.call_args
    assert "Invalid or expired pairing code" in args[0].content

    # 3. Create a valid pairing code
    code = generate_pairing_code(expires_in_seconds=60)

    mock_config = SimpleNamespace(
        channels=SimpleNamespace(dummy=SimpleNamespace(allow_from=[]))
    )

    with (
        patch("amberclaw.config.loader.get_config_path", return_value=mock_config_path),
        patch("amberclaw.config.loader.load_config", return_value=mock_config),
        patch("amberclaw.config.loader.save_config") as mock_save,
    ):
        mock_config_path.touch()

        msg_valid = InboundMessage(
            channel="dummy",
            sender_id="user123",
            chat_id="chat123",
            content=f"/pair {code}",
        )

        bus.publish_outbound.reset_mock()
        await agent._handle_pairing(msg_valid)

        # Verify in-memory config update
        assert "user123" in channels_cfg.dummy.allow_from

        # Verify load_config and save_config were called
        mock_save.assert_called_once_with(mock_config, mock_config_path)
        assert "user123" in mock_config.channels.dummy.allow_from

        # Verify success reply
        args, _ = bus.publish_outbound.call_args
        assert "successfully paired" in args[0].content
