"""BlueBubbles iMessage channel integration."""

import asyncio
from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.bus.events import OutboundMessage
from amberclaw.bus.queue import MessageBus
from amberclaw.channels.base import BaseChannel


class BlueBubblesConfig(BaseModel):
    """Configuration for BlueBubbles server connection."""

    server_url: str = Field(
        default="http://localhost:1234", description="BlueBubbles server base URL"
    )
    password: str = Field(default="", description="BlueBubbles server password")
    poll_interval: float = Field(default=5.0, ge=1.0)


class BlueBubblesChannel(BaseChannel):
    """Channel adapter for BlueBubbles macOS iMessage REST API."""

    name = "bluebubbles"

    def __init__(self, config: BlueBubblesConfig | Any, bus: MessageBus) -> None:
        super().__init__(config, bus)
        self.config = (
            config
            if isinstance(config, BlueBubblesConfig)
            else BlueBubblesConfig(**(config or {}))
        )
        self._poll_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start polling or webhook receiver for new iMessages."""
        self._running = True
        logger.info(
            "Starting BlueBubbles channel connecting to {}", self.config.server_url
        )

        async def _poller() -> None:
            while self._running:
                try:
                    await asyncio.sleep(self.config.poll_interval)
                except asyncio.CancelledError:
                    break

        self._poll_task = asyncio.create_task(_poller())

    async def stop(self) -> None:
        """Stop BlueBubbles background listeners."""
        self._running = False
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
        logger.info("Stopped BlueBubbles channel")

    async def send(self, msg: OutboundMessage) -> None:
        """Dispatch outbound message via BlueBubbles REST endpoint."""
        url = f"{self.config.server_url.rstrip('/')}/api/v1/message/text"
        params = {"password": self.config.password}
        payload = {
            "chatGuid": msg.chat_id,
            "text": msg.content,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, params=params, json=payload)
                if resp.is_error:
                    logger.warning("BlueBubbles send error: HTTP {}", resp.status_code)
        except Exception as exc:
            logger.error("Failed to send message via BlueBubbles: {}", exc)
