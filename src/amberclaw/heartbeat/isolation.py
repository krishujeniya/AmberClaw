"""Process isolation and zombie task detection for Heartbeat subsystem."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.heartbeat.engine import HeartbeatStatus


class IsolationRecord(BaseModel):
    """Metadata regarding an isolated process."""

    process_id: str
    isolated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reason: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProcessIsolationManager:
    """Detects unresponsive or dead background processes and isolates them."""

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self.timeout = timedelta(seconds=timeout_seconds)
        self._isolated: dict[str, IsolationRecord] = {}

    def check_for_zombies(
        self, statuses: dict[str, HeartbeatStatus]
    ) -> list[str]:
        """Find processes that have missed their heartbeat threshold."""
        now = datetime.now(UTC)
        zombie_ids: list[str] = []

        for pid, status in statuses.items():
            if pid in self._isolated:
                continue

            last_seen = status.last_ping
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=UTC)

            if now - last_seen > self.timeout:
                zombie_ids.append(pid)

        return zombie_ids

    def isolate_process(
        self,
        process_id: str,
        reason: str = "Heartbeat timeout exceeded",
        tasks: dict[str, asyncio.Task] | None = None,
    ) -> IsolationRecord:
        """Isolate and cancel the hung process task."""
        record = IsolationRecord(process_id=process_id, reason=reason)
        self._isolated[process_id] = record

        if tasks and process_id in tasks:
            task = tasks[process_id]
            if not task.done():
                logger.warning(
                    f"Isolating and cancelling zombie process task: {process_id} (reason: {reason})"
                )
                task.cancel()

        return record

    def is_isolated(self, process_id: str) -> bool:
        """Check if process is currently isolated."""
        return process_id in self._isolated

    def release(self, process_id: str) -> bool:
        """Release a process from isolation."""
        return bool(self._isolated.pop(process_id, None))

    def get_isolated_records(self) -> list[IsolationRecord]:
        """Return list of all current isolation records."""
        return list(self._isolated.values())
