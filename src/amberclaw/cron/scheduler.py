"""Core scheduling loop and timer coordinator for Cron jobs."""

from __future__ import annotations

import asyncio

from loguru import logger

from amberclaw.cron.audit import CronAuditLogger
from amberclaw.cron.delivery import CronDeliveryRouter
from amberclaw.cron.service import CronService


class CronScheduler:
    """Async scheduler coordinating recurring task dispatch, audit, and delivery."""

    def __init__(
        self,
        service: CronService,
        audit_logger: CronAuditLogger | None = None,
        delivery_router: CronDeliveryRouter | None = None,
    ) -> None:
        self.service = service
        self.audit = audit_logger or CronAuditLogger()
        self.delivery = delivery_router or CronDeliveryRouter()
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the cron service and scheduler loop."""
        if self._running:
            return
        self._running = True
        await self.service.start()
        logger.info("CronScheduler started.")

    def stop(self) -> None:
        """Stop the scheduler and underlying cron service."""
        self._running = False
        self.service.stop()
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("CronScheduler stopped.")

    async def execute_job_now(self, job_id: str, force: bool = False) -> bool:
        """Manually trigger a job and record audit telemetry."""
        start_time = asyncio.get_event_loop().time()
        success = await self.service.run_job(job_id, force=force)
        duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000

        status = "ok" if success else "error"
        self.audit.record_run(job_id=job_id, status=status, duration_ms=duration_ms)
        return success
