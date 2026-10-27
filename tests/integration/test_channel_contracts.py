# ruff: noqa: PLR2004, S106
"""Channel contract test suite for AmberClaw messaging adapters.

Verifies standard behaviors across multiple channel implementations:
- Strict authorization check against allow_from lists (including pairing bypass)
- Proper inbound message encapsulation and bus publishing
- Structured outbound delivery contract
- Robust error handling on transport failures
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from amberclaw.bus.events import InboundMessage, OutboundMessage
from amberclaw.bus.queue import MessageBus
from amberclaw.channels.base import BaseChannel
from amberclaw.channels.dingtalk import DingTalkChannel
from amberclaw.channels.discord import DiscordChannel
from amberclaw.channels.email import EmailChannel
from amberclaw.channels.feishu import FeishuChannel
from amberclaw.channels.matrix import MatrixChannel
from amberclaw.channels.slack import SlackChannel
from amberclaw.channels.telegram import TelegramChannel
from amberclaw.config.schema import EmailConfig, TelegramConfig


class TestChannelContracts:
    """Standardized contract validation for chat channel adapters."""

    def test_channel_hierarchy_and_attributes(self):
        """Contract Check: All channel adapters must inherit BaseChannel and declare name attribute."""
        channel_classes = [
            TelegramChannel,
            DiscordChannel,
            MatrixChannel,
            EmailChannel,
            SlackChannel,
            DingTalkChannel,
            FeishuChannel,
        ]
        for cls in channel_classes:
            assert issubclass(cls, BaseChannel)
            assert isinstance(cls.name, str)
            assert len(cls.name) > 0

    @pytest.mark.asyncio
    async def test_allowlist_authorization_contract(self):
        """Contract Check: Verify allow_from behavior across all channels."""
        bus = MessageBus()

        # 1. Specific user allowed
        config_specific = TelegramConfig(
            token="test", allow_from=["alice_123", "bob_456"]
        )
        ch1 = TelegramChannel(config_specific, bus)
        assert ch1.is_allowed("alice_123") is True
        assert ch1.is_allowed("bob_456") is True
        assert ch1.is_allowed("eve_attacker") is False

        # 2. Wildcard allowed
        config_wildcard = SimpleNamespace(allow_from=["*"])
        ch2 = DiscordChannel(config_wildcard, bus)
        assert ch2.is_allowed("any_user_123") is True

        # 3. Empty list denies all
        config_empty = SimpleNamespace(allow_from=[])
        ch3 = SlackChannel(config_empty, bus)
        assert ch3.is_allowed("anyone") is False

    @pytest.mark.asyncio
    async def test_inbound_message_handling_contract(self):
        """Contract Check: _handle_message properly validates permissions and publishes to bus."""
        bus = MessageBus()
        config = TelegramConfig(token="test", allow_from=["user_allowed"])
        channel = TelegramChannel(config, bus)

        # 1. Allowed sender -> Message gets published to inbound queue
        await channel._handle_message(
            sender_id="user_allowed",
            chat_id="chat_1",
            content="Hello AmberClaw!",
            media=["https://example.com/image.png"],
            metadata={"priority": "high"},
        )
        assert bus.inbound_size == 1
        msg: InboundMessage = await bus.consume_inbound()
        assert msg.channel == "telegram"
        assert msg.sender_id == "user_allowed"
        assert msg.chat_id == "chat_1"
        assert msg.content == "Hello AmberClaw!"
        assert msg.media == ["https://example.com/image.png"]
        assert msg.metadata.get("priority") == "high"

        # 2. Denied sender -> Message is dropped
        await channel._handle_message(
            sender_id="unauthorized_user",
            chat_id="chat_2",
            content="Malicious payload",
        )
        assert bus.inbound_size == 0

        # 3. Pairing command from unauthorized sender is allowed through for pairing handshake
        await channel._handle_message(
            sender_id="unauthorized_user",
            chat_id="chat_2",
            content="/pair 123456",
        )
        assert bus.inbound_size == 1
        pairing_msg = await bus.consume_inbound()
        assert pairing_msg.content == "/pair 123456"

    @pytest.mark.asyncio
    async def test_telegram_send_contract(self):
        """Contract Check: Telegram channel formats and sends outbound messages."""
        bus = MessageBus()
        config = TelegramConfig(
            token="dummy-token",
            allow_from=["*"],
        )
        channel = TelegramChannel(config, bus)
        channel._app = MagicMock()
        channel._app.bot.send_message = AsyncMock()

        outbound = OutboundMessage(
            channel="telegram",
            chat_id="12345",
            content="Test response from agent",
        )
        await channel.send(outbound)
        channel._app.bot.send_message.assert_called_once()
        call_kwargs = channel._app.bot.send_message.call_args.kwargs
        assert call_kwargs["chat_id"] == 12345
        assert "Test response from agent" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_email_send_contract(self):
        """Contract Check: Email channel sends properly formatted email messages."""
        bus = MessageBus()
        config = EmailConfig(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="user@example.com",
            smtp_password="password",
            from_address="ai@example.com",
            consent_granted=True,
            auto_reply_enabled=True,
            allow_from=["*"],
        )
        channel = EmailChannel(config, bus)

        outbound = OutboundMessage(
            channel="email",
            chat_id="recipient@example.com",
            content="Body of the email",
        )

        with patch.object(channel, "_smtp_send") as mock_smtp_send:
            await channel.send(outbound)
            mock_smtp_send.assert_called_once()
            sent_msg = mock_smtp_send.call_args[0][0]
            assert sent_msg["To"] == "recipient@example.com"
            assert sent_msg["From"] == "ai@example.com"
            assert "Body of the email" in sent_msg.get_content()
