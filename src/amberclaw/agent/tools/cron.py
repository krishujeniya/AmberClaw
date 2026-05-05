"""Cron tool for scheduling reminders and tasks."""

from contextvars import ContextVar
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field

from amberclaw.agent.tools.base import PydanticTool
from amberclaw.cron.service import CronService
from amberclaw.cron.types import CronSchedule


class CronArgs(BaseModel):
    """Arguments for the cron tool."""

    action: Literal["add", "list", "remove"] = Field(..., description="Action to perform")
    message: Optional[str] = Field(None, description="Reminder message (for add)")
    every_seconds: Optional[int] = Field(
        None, description="Interval in seconds (for recurring tasks)"
    )
    cron_expr: Optional[str] = Field(
        None, description="Cron expression like '0 9 * * *' (for scheduled tasks)"
    )
    tz: Optional[str] = Field(
        None, description="IANA timezone for cron expressions (e.g. 'America/Vancouver')"
    )
    at: Optional[str] = Field(
        None, description="ISO datetime for one-time execution (e.g. '2026-02-12T10:30:00')"
    )
    job_id: Optional[str] = Field(None, description="Job ID (for remove)")


class CronTool(PydanticTool):
    """Tool to schedule reminders and recurring tasks."""

    @property
    def name(self) -> str:
        return "cron"

    @property
    def description(self) -> str:
        return "Schedule reminders and recurring tasks. Actions: add, list, remove."

    @property
    def args_schema(self) -> type[CronArgs]:
        return CronArgs

    def __init__(self, cron_service: CronService):
        super().__init__()
        self._cron = cron_service
        self._channel = ""
        self._chat_id = ""
        self._in_cron_context: ContextVar[bool] = ContextVar("cron_in_context", default=False)

    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the current session context for delivery."""
        self._channel = channel
        self._chat_id = chat_id

    def set_cron_context(self, active: bool):
        """Mark whether the tool is executing inside a cron job callback."""
        return self._in_cron_context.set(active)

    def reset_cron_context(self, token) -> None:
        """Restore previous cron context."""
        self._in_cron_context.reset(token)

    async def run(self, args: CronArgs) -> str:
        if args.action == "add":
            if self._in_cron_context.get():
                return "Error: cannot schedule new jobs from within a cron job execution"
            return self._add_job(args)
        elif args.action == "list":
            return self._list_jobs()
        elif args.action == "remove":
            return self._remove_job(args.job_id)
        return f"Unknown action: {args.action}"

    def _add_job(self, args: CronArgs) -> str:
        if not args.message:
            return "Error: message is required for add"
        if not self._channel or not self._chat_id:
            return "Error: no session context (channel/chat_id)"
        if args.tz and not args.cron_expr:
            return "Error: tz can only be used with cron_expr"
        if args.tz:
            from zoneinfo import ZoneInfo

            try:
                ZoneInfo(args.tz)
            except (KeyError, Exception):
                return f"Error: unknown timezone '{args.tz}'"

        # Build schedule
        delete_after = False
        if args.every_seconds:
            schedule = CronSchedule(kind="every", every_ms=args.every_seconds * 1000)
        elif args.cron_expr:
            schedule = CronSchedule(kind="cron", expr=args.cron_expr, tz=args.tz)
        elif args.at:
            try:
                dt = datetime.fromisoformat(args.at)
            except ValueError:
                return f"Error: invalid ISO datetime format '{args.at}'. Expected format: YYYY-MM-DDTHH:MM:SS"
            at_ms = int(dt.timestamp() * 1000)
            schedule = CronSchedule(kind="at", at_ms=at_ms)
            delete_after = True
        else:
            return "Error: either every_seconds, cron_expr, or at is required"

        job = self._cron.add_job(
            name=args.message[:30],
            schedule=schedule,
            message=args.message,
            deliver=True,
            channel=self._channel,
            to=self._chat_id,
            delete_after_run=delete_after,
        )
        return f"Created job '{job.name}' (id: {job.id})"

    def _list_jobs(self) -> str:
        jobs = self._cron.list_jobs()
        if not jobs:
            return "No scheduled jobs."
        lines = [f"- {j.name} (id: {j.id}, {j.schedule.kind})" for j in jobs]
        return "Scheduled jobs:\n" + "\n".join(lines)

    def _remove_job(self, job_id: str | None) -> str:
        if not job_id:
            return "Error: job_id is required for remove"
        if self._cron.remove_job(job_id):
            return f"Removed job {job_id}"
        return f"Job {job_id} not found"
