"""Home Assistant webhook and notification channel integration."""

from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.bus.events import OutboundMessage
from amberclaw.bus.queue import MessageBus
from amberclaw.channels.base import BaseChannel


class HomeAssistantConfig(BaseModel):
    """Configuration for Home Assistant integration."""

    base_url: str = Field(
        default="http://homeassistant.local:8123",
        description="Base URL of Home Assistant",
    )
    long_lived_token: str = Field(
        default="", description="Home Assistant Long-Lived Access Token"
    )
    notify_service: str = Field(
        default="notify.notify", description="Default notification service entity"
    )


class HomeAssistantChannel(BaseChannel):
    """Channel adapter for Home Assistant REST events and state notifications."""

    name = "homeassistant"

    def __init__(self, config: HomeAssistantConfig | Any, bus: MessageBus) -> None:
        super().__init__(config, bus)
        self.config = (
            config
            if isinstance(config, HomeAssistantConfig)
            else HomeAssistantConfig(**(config or {}))
        )

    async def start(self) -> None:
        """Start Home Assistant channel."""
        self._running = True
        logger.info("Home Assistant channel started for {}", self.config.base_url)

    async def stop(self) -> None:
        """Stop Home Assistant channel."""
        self._running = False
        logger.info("Home Assistant channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """Post message to Home Assistant notification service or conversation agent."""
        service_target = (
            msg.metadata.get("service") if msg.metadata else self.config.notify_service
        )
        url = f"{self.config.base_url.rstrip('/')}/api/services/{service_target.replace('.', '/')}"

        headers = {
            "Authorization": f"Bearer {self.config.long_lived_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "message": msg.content,
            "title": msg.metadata.get("title", "AmberClaw Alert")
            if msg.metadata
            else "AmberClaw Alert",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.is_error:
                    logger.warning(
                        "Home Assistant notification returned HTTP {}", resp.status_code
                    )
        except Exception as exc:
            logger.error("Failed to send message to Home Assistant: {}", exc)
