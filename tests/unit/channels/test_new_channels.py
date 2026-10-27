# ruff: noqa: S106
"""Unit tests for newly implemented chat channels (BlueBubbles, HomeAssistant, Mattermost, Signal, SMS, WeChat, Proxy)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from amberclaw.bus.events import OutboundMessage
from amberclaw.bus.queue import MessageBus
from amberclaw.channels.bluebubbles import BlueBubblesChannel, BlueBubblesConfig
from amberclaw.channels.homeassistant import HomeAssistantChannel, HomeAssistantConfig
from amberclaw.channels.mattermost import MattermostChannel, MattermostConfig
from amberclaw.channels.proxy import ChannelProxy, ChannelProxyConfig
from amberclaw.channels.signal import SignalChannel, SignalConfig
from amberclaw.channels.sms import SMSChannel, SMSConfig
from amberclaw.channels.wechat import WeChatChannel, WeChatConfig


@pytest.fixture
def mock_bus() -> MessageBus:
    bus = MessageBus()
    bus.publish_inbound = AsyncMock()
    return bus


@pytest.mark.asyncio
async def test_bluebubbles_lifecycle(mock_bus: MessageBus):
    config = BlueBubblesConfig(server_url="http://mock-mac:1234", password="pass")
    channel = BlueBubblesChannel(config=config, bus=mock_bus)

    await channel.start()
    assert channel._running is True

    msg = OutboundMessage(
        channel="bluebubbles", chat_id="chat-guid-1", content="Hello iMessage"
    )
    # Send executes with error catch without crashing
    await channel.send(msg)

    await channel.stop()
    assert channel._running is False


@pytest.mark.asyncio
async def test_homeassistant_lifecycle(mock_bus: MessageBus):
    config = HomeAssistantConfig(
        base_url="http://hass.local:8123", long_lived_token="tok"
    )
    channel = HomeAssistantChannel(config=config, bus=mock_bus)

    await channel.start()
    assert channel._running is True

    msg = OutboundMessage(
        channel="homeassistant", chat_id="default", content="Turn on lights"
    )
    await channel.send(msg)

    await channel.stop()
    assert channel._running is False


@pytest.mark.asyncio
async def test_mattermost_lifecycle(mock_bus: MessageBus):
    config = MattermostConfig(
        server_url="http://mattermost.local:8065", bot_token="tok"
    )
    channel = MattermostChannel(config=config, bus=mock_bus)

    await channel.start()
    assert channel._running is True

    msg = OutboundMessage(
        channel="mattermost", chat_id="channel-xyz", content="Alert posted"
    )
    await channel.send(msg)

    await channel.stop()
    assert channel._running is False


@pytest.mark.asyncio
async def test_signal_lifecycle(mock_bus: MessageBus):
    config = SignalConfig(endpoint="http://signal.local:8080", account="+1234567890")
    channel = SignalChannel(config=config, bus=mock_bus)

    await channel.start()
    assert channel._running is True

    msg = OutboundMessage(
        channel="signal", chat_id="+1987654321", content="Secure Signal Msg"
    )
    await channel.send(msg)

    await channel.stop()
    assert channel._running is False


@pytest.mark.asyncio
async def test_sms_lifecycle(mock_bus: MessageBus):
    config = SMSConfig(
        account_sid="AC12345", auth_token="tok123", from_number="+1000000000"
    )
    channel = SMSChannel(config=config, bus=mock_bus)

    await channel.start()
    assert channel._running is True

    msg = OutboundMessage(
        channel="sms", chat_id="+1999999999", content="SMS Notification"
    )
    await channel.send(msg)

    await channel.stop()
    assert channel._running is False


@pytest.mark.asyncio
async def test_wechat_lifecycle(mock_bus: MessageBus):
    config = WeChatConfig(
        webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=mock"
    )
    channel = WeChatChannel(config=config, bus=mock_bus)

    await channel.start()
    assert channel._running is True

    msg = OutboundMessage(
        channel="wechat", chat_id="default", content="WeChat Work message"
    )
    await channel.send(msg)

    await channel.stop()
    assert channel._running is False


@pytest.mark.asyncio
async def test_channel_proxy(mock_bus: MessageBus):
    config = ChannelProxyConfig(proxy_id="virtual-proxy")
    proxy = ChannelProxy(config=config, bus=mock_bus)

    mock_target = MagicMock()
    mock_target.send = AsyncMock()
    proxy.register_target_channel("target_chan", mock_target)

    await proxy.start()

    # Route outbound
    msg = OutboundMessage(
        channel="proxy",
        chat_id="chat-1",
        content="Routed message",
        metadata={"target_channel": "target_chan"},
    )
    await proxy.send(msg)
    mock_target.send.assert_awaited_once_with(msg)

    # Route inbound
    inbound = await proxy.route_inbound_payload(
        source_channel="webhook",
        sender_id="ext-user",
        chat_id="chan-42",
        content="Incoming webhook",
    )
    assert inbound.channel == "webhook"
    assert inbound.content == "Incoming webhook"
    mock_bus.publish_inbound.assert_awaited_once()

    await proxy.stop()
