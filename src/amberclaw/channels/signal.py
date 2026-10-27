"""Signal Messenger channel implementation using signal-cli JSON-RPC REST API."""

import asyncio
from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.bus.events import OutboundMessage
from amberclaw.bus.queue import MessageBus
from amberclaw.channels.base import BaseChannel


class SignalConfig(BaseModel):
    """Configuration for Signal REST gateway."""

    endpoint: str = Field(
        default="http://localhost:8080", description="signal-cli REST API endpoint"
    )
    account: str = Field(
        default="", description="Registered Signal phone number (e.g. +1234567890)"
    )
    poll_interval: float = Field(default=3.0, ge=1.0)


class SignalChannel(BaseChannel):
    """Channel adapter for end-to-end encrypted Signal messaging via signal-cli daemon."""

    name = "signal"

    def __init__(self, config: SignalConfig | Any, bus: MessageBus) -> None:
        super().__init__(config, bus)
        self.config = (
            config
            if isinstance(config, SignalConfig)
            else SignalConfig(**(config or {}))
        )
        self._listener_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start listening for incoming Signal messages."""
        self._running = True
        logger.info("Signal channel started for account '{}'", self.config.account)

        async def _poller() -> None:
            while self._running:
                try:
                    await asyncio.sleep(self.config.poll_interval)
                except asyncio.CancelledError:
                    break

        self._listener_task = asyncio.create_task(_poller())

    async def stop(self) -> None:
        """Stop Signal listener."""
        self._running = False
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
        logger.info("Signal channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """Transmit outbound Signal message."""
        url = f"{self.config.endpoint.rstrip('/')}/v2/send"
        payload = {
            "message": msg.content,
            "number": self.config.account,
            "recipients": [msg.chat_id],
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload)
                if resp.is_error:
                    logger.warning("Signal send error: HTTP {}", resp.status_code)
        except Exception as exc:
            logger.error("Failed to send message via Signal: {}", exc)
