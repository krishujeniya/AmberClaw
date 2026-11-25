"""SMS text messaging channel adapter via Twilio or generic SMS gateway."""

from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.bus.events import OutboundMessage
from amberclaw.bus.queue import MessageBus
from amberclaw.channels.base import BaseChannel


class SMSConfig(BaseModel):
    """Configuration for SMS messaging gateway."""

    account_sid: str = Field(
        default="", description="Twilio Account SID or gateway username"
    )
    auth_token: str = Field(
        default="", description="Twilio Auth Token or gateway password"
    )
    from_number: str = Field(
        default="", description="Registered sender phone number in E.164 format"
    )
    custom_endpoint: str | None = Field(
        default=None, description="Custom REST API endpoint override"
    )


class SMSChannel(BaseChannel):
    """Channel adapter delivering cellular SMS alerts and interactive turns."""

    name = "sms"

    def __init__(self, config: SMSConfig | Any, bus: MessageBus) -> None:
        super().__init__(config, bus)
        self.config = (
            config if isinstance(config, SMSConfig) else SMSConfig(**(config or {}))
        )

    async def start(self) -> None:
        """Start SMS channel listener."""
        self._running = True
        logger.info("SMS channel active for sender '{}'", self.config.from_number)

    async def stop(self) -> None:
        """Stop SMS channel."""
        self._running = False
        logger.info("SMS channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """Send an SMS to recipient phone number."""
        if not self.config.account_sid or not self.config.auth_token:
            logger.warning("SMS channel cannot send: missing account_sid or auth_token")
            return

        endpoint = self.config.custom_endpoint or (
            f"https://api.twilio.com/2010-04-01/Accounts/{self.config.account_sid}/Messages.json"
        )
        data = {
            "From": self.config.from_number,
            "To": msg.chat_id,
            "Body": msg.content,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    endpoint,
                    data=data,
                    auth=(self.config.account_sid, self.config.auth_token),
                )
                if resp.is_error:
                    logger.warning("SMS gateway returned HTTP {}", resp.status_code)
        except Exception as exc:
            logger.error("Failed to send SMS message: {}", exc)
