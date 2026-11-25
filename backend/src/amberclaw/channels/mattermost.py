"""Mattermost webhook and bot channel integration."""

from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.bus.events import OutboundMessage
from amberclaw.bus.queue import MessageBus
from amberclaw.channels.base import BaseChannel


class MattermostConfig(BaseModel):
    """Configuration for Mattermost channel."""

    server_url: str = Field(
        default="http://localhost:8065", description="Mattermost server URL"
    )
    bot_token: str = Field(default="", description="Bot account personal access token")
    incoming_webhook_url: str | None = Field(
        default=None, description="Incoming webhook URL fallback"
    )


class MattermostChannel(BaseChannel):
    """Channel adapter for Mattermost REST API v4 and incoming webhooks."""

    name = "mattermost"

    def __init__(self, config: MattermostConfig | Any, bus: MessageBus) -> None:
        super().__init__(config, bus)
        self.config = (
            config
            if isinstance(config, MattermostConfig)
            else MattermostConfig(**(config or {}))
        )

    async def start(self) -> None:
        """Initialize Mattermost channel."""
        self._running = True
        logger.info("Mattermost channel started for {}", self.config.server_url)

    async def stop(self) -> None:
        """Stop Mattermost channel."""
        self._running = False
        logger.info("Mattermost channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """Deliver message to designated channel ID or incoming webhook."""
        if self.config.incoming_webhook_url:
            await self._send_via_webhook(msg)
        else:
            await self._send_via_api(msg)

    async def _send_via_webhook(self, msg: OutboundMessage) -> None:
        payload = {"text": msg.content}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(self.config.incoming_webhook_url, json=payload)
        except Exception as exc:
            logger.error("Mattermost webhook delivery failure: {}", exc)

    async def _send_via_api(self, msg: OutboundMessage) -> None:
        url = f"{self.config.server_url.rstrip('/')}/api/v4/posts"
        headers = {
            "Authorization": f"Bearer {self.config.bot_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "channel_id": msg.chat_id,
            "message": msg.content,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.is_error:
                    logger.warning(
                        "Mattermost API post returned HTTP {}", resp.status_code
                    )
        except Exception as exc:
            logger.error("Mattermost API delivery failure: {}", exc)
