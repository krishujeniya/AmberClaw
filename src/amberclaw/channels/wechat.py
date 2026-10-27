"""WeChat Work / Enterprise WeChat webhook and messaging channel adapter."""

from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.bus.events import OutboundMessage
from amberclaw.bus.queue import MessageBus
from amberclaw.channels.base import BaseChannel


class WeChatConfig(BaseModel):
    """Configuration for WeChat Work bot or enterprise gateway."""

    webhook_url: str = Field(
        default="", description="WeChat Work custom robot webhook URL"
    )
    corp_id: str | None = Field(default=None, description="Enterprise CorpID")
    corp_secret: str | None = Field(default=None, description="Enterprise CorpSecret")
    agent_id: int | None = Field(
        default=None, description="Enterprise application AgentID"
    )


class WeChatChannel(BaseChannel):
    """Channel adapter for WeChat Work (企业微信) robot and enterprise messaging."""

    name = "wechat"

    def __init__(self, config: WeChatConfig | Any, bus: MessageBus) -> None:
        super().__init__(config, bus)
        self.config = (
            config
            if isinstance(config, WeChatConfig)
            else WeChatConfig(**(config or {}))
        )

    async def start(self) -> None:
        """Initialize WeChat channel."""
        self._running = True
        logger.info("WeChat channel started")

    async def stop(self) -> None:
        """Stop WeChat channel."""
        self._running = False
        logger.info("WeChat channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """Dispatch message to WeChat robot webhook."""
        if not self.config.webhook_url:
            logger.warning("WeChat channel cannot send: missing webhook_url")
            return

        payload = {
            "msgtype": "text",
            "text": {
                "content": msg.content,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self.config.webhook_url, json=payload)
                if resp.is_error:
                    logger.warning("WeChat webhook returned HTTP {}", resp.status_code)
        except Exception as exc:
            logger.error("Failed to send WeChat message: {}", exc)
