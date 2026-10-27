# ruff: noqa: PLR0913
"""High-level Cron manager facade for agent tasks."""

from __future__ import annotations

from pathlib import Path

from amberclaw.cron.audit import CronAuditLogger
from amberclaw.cron.delivery import CronDeliveryRouter
from amberclaw.cron.nlp import parse_natural_schedule
from amberclaw.cron.scheduler import CronScheduler
from amberclaw.cron.service import CronService
from amberclaw.cron.types import CronJob


class CronManager:
    """Facade for managing cron jobs, parsing human schedules, and dispatching execution."""

    def __init__(self, workspace_or_store: Path | str | None = None) -> None:
        if workspace_or_store is None:
            store_path = Path("~/.amberclaw/cron_jobs.json").expanduser()
        elif isinstance(workspace_or_store, str) and not workspace_or_store.endswith(".json"):
            store_path = Path(workspace_or_store) / "cron" / "jobs.json"
        else:
            store_path = Path(workspace_or_store)

        store_path.parent.mkdir(parents=True, exist_ok=True)
        self.service = CronService(store_path=store_path)
        self.audit = CronAuditLogger()
        self.delivery = CronDeliveryRouter()
        self.scheduler = CronScheduler(
            service=self.service,
            audit_logger=self.audit,
            delivery_router=self.delivery,
        )

    def schedule_task(
        self,
        name: str,
        natural_schedule: str,
        message: str,
        channel: str | None = None,
        to: str | None = None,
        delete_after_run: bool = False,
    ) -> CronJob:
        """Schedule a task using natural language schedule syntax."""
        schedule = parse_natural_schedule(natural_schedule)
        return self.service.add_job(
            name=name,
            schedule=schedule,
            message=message,
            deliver=bool(channel),
            channel=channel,
            to=to,
            delete_after_run=delete_after_run,
        )

    def list_jobs(self, include_disabled: bool = False) -> list[CronJob]:
        """List active or all jobs."""
        return self.service.list_jobs(include_disabled=include_disabled)

    def remove_job(self, job_id: str) -> bool:
        """Remove a job by ID."""
        return self.service.remove_job(job_id)

    def enable_job(self, job_id: str, enabled: bool = True) -> CronJob | None:
        """Toggle job enabled state."""
        return self.service.enable_job(job_id, enabled=enabled)
