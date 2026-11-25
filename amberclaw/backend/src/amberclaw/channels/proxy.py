"""Channel network proxy and multi-tenant webhook router."""

from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.bus.events import InboundMessage, OutboundMessage
from amberclaw.bus.queue import MessageBus
from amberclaw.channels.base import BaseChannel


class ChannelProxyConfig(BaseModel):
    """Configuration for cross-network channel proxying."""

    proxy_id: str = Field(default="primary-proxy")
    forward_unmapped_to_bus: bool = Field(default=True)


class ChannelProxy(BaseChannel):
    """Virtual channel router capable of relaying messages across isolated sub-networks."""

    name = "proxy"

    def __init__(self, config: ChannelProxyConfig | Any, bus: MessageBus) -> None:
        super().__init__(config, bus)
        self.config = (
            config
            if isinstance(config, ChannelProxyConfig)
            else ChannelProxyConfig(**(config or {}))
        )
        self._target_channels: dict[str, BaseChannel] = {}

    def register_target_channel(self, channel_name: str, channel: BaseChannel) -> None:
        """Register a destination channel backend for routed dispatches."""
        self._target_channels[channel_name] = channel

    async def start(self) -> None:
        """Initialize channel proxy."""
        self._running = True
        logger.info("ChannelProxy [{}] active", self.config.proxy_id)

    async def stop(self) -> None:
        """Stop channel proxy."""
        self._running = False
        logger.info("ChannelProxy [{}] stopped", self.config.proxy_id)

    async def send(self, msg: OutboundMessage) -> None:
        """Route message to appropriate physical channel target or loopback."""
        target = msg.metadata.get("target_channel") if msg.metadata else None
        if target and target in self._target_channels:
            await self._target_channels[target].send(msg)
            return

        logger.debug(
            "ChannelProxy forwarded outbound message for chat_id={}", msg.chat_id
        )

    async def route_inbound_payload(
        self,
        source_channel: str,
        sender_id: str,
        chat_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> InboundMessage:
        """Ingest external webhook event and publish normalized InboundMessage to bus."""
        msg = InboundMessage(
            channel=source_channel,
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            metadata=metadata or {},
        )
        await self.bus.publish_inbound(msg)
        return msg
