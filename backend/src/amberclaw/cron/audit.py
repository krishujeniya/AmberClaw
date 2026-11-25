"""Audit logging and telemetry for cron job executions."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from loguru import logger


@dataclass
class CronAuditRecord:
    """Execution telemetry record for a scheduled cron job."""

    job_id: str
    run_at_iso: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    status: Literal["ok", "error", "skipped"] = "ok"
    duration_ms: float = 0.0
    error: str | None = None


class CronAuditLogger:
    """Manages audit records and run histories for scheduled jobs."""

    def __init__(self, log_path: Path | None = None) -> None:
        self.log_path = log_path
        self._history: dict[str, list[CronAuditRecord]] = {}

    def record_run(
        self,
        job_id: str,
        status: Literal["ok", "error", "skipped"],
        duration_ms: float = 0.0,
        error: str | None = None,
    ) -> CronAuditRecord:
        """Record a completed or failed cron run."""
        rec = CronAuditRecord(
            job_id=job_id,
            status=status,
            duration_ms=duration_ms,
            error=error,
        )
        if job_id not in self._history:
            self._history[job_id] = []
        self._history[job_id].append(rec)

        if self.log_path:
            try:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                with self.log_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(asdict(rec)) + "\n")
            except Exception as ex:
                logger.warning(f"Failed to append cron audit record: {ex}")

        return rec

    def get_job_history(self, job_id: str, limit: int = 50) -> list[CronAuditRecord]:
        """Retrieve recent execution history for a job."""
        return self._history.get(job_id, [])[-limit:]
