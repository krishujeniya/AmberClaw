"""Delivery routing for cron job execution results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from amberclaw.cron.types import CronPayload


@dataclass
class CronDeliveryReceipt:
    """Receipt acknowledging delivery of job output to a target destination."""

    job_id: str
    destination: str
    delivered: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    error: str | None = None


class CronDeliveryRouter:
    """Routes cron job outputs to channels or webhooks."""

    def __init__(self, channel_manager: Any | None = None) -> None:
        self.channel_manager = channel_manager

    async def route_delivery(
        self,
        job_id: str,
        payload: CronPayload,
        result_text: str,
    ) -> CronDeliveryReceipt:
        """Deliver the execution output according to payload preferences."""
        if not payload.deliver or not payload.channel:
            return CronDeliveryReceipt(
                job_id=job_id,
                destination="none",
                delivered=True,
            )

        destination = f"{payload.channel}://{payload.to or 'broadcast'}"

        if self.channel_manager:
            try:
                # Dispatch through channel manager if available
                await self.channel_manager.send_message(
                    channel=payload.channel,
                    to=payload.to,
                    content=result_text,
                )
                logger.info(f"Delivered cron {job_id} result to {destination}")
                return CronDeliveryReceipt(
                    job_id=job_id,
                    destination=destination,
                    delivered=True,
                )
            except Exception as ex:
                logger.error(f"Failed to deliver cron {job_id} result to {destination}: {ex}")
                return CronDeliveryReceipt(
                    job_id=job_id,
                    destination=destination,
                    delivered=False,
                    error=str(ex),
                )

        logger.debug(f"Simulated cron result delivery to {destination}: {result_text[:60]}")
        return CronDeliveryReceipt(
            job_id=job_id,
            destination=destination,
            delivered=True,
        )
