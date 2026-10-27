"""Process recovery and automated restart backoff for Heartbeat subsystem."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


class RecoveryAttempt(BaseModel):
    """Details of a process recovery attempt."""

    process_id: str
    attempt_number: int
    scheduled_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    success: bool = False
    error: str | None = None


class ProcessRecoveryManager:
    """Manages restart policies, exponential backoff, and circuit breaker for failed processes."""

    def __init__(
        self,
        max_attempts: int = 5,
        base_backoff_seconds: float = 1.0,
        max_backoff_seconds: float = 60.0,
    ) -> None:
        self.max_attempts = max_attempts
        self.base_backoff = base_backoff_seconds
        self.max_backoff = max_backoff_seconds
        self._attempts: dict[str, int] = {}
        self._tripped_circuits: set[str] = set()

    def get_backoff_delay(self, process_id: str) -> float:
        """Calculate exponential backoff delay based on current attempt count."""
        attempts = self._attempts.get(process_id, 0)
        delay = self.base_backoff * (2**attempts)
        return min(delay, self.max_backoff)

    def can_recover(self, process_id: str) -> bool:
        """Check if process can be recovered without violating circuit breaker."""
        if process_id in self._tripped_circuits:
            return False
        return self._attempts.get(process_id, 0) < self.max_attempts

    def record_attempt(self, process_id: str, success: bool) -> None:
        """Record outcome of a recovery attempt."""
        if success:
            self._attempts[process_id] = 0
            self._tripped_circuits.discard(process_id)
        else:
            curr = self._attempts.get(process_id, 0) + 1
            self._attempts[process_id] = curr
            if curr >= self.max_attempts:
                logger.error(
                    f"Circuit breaker tripped for process {process_id} after {curr} failed restart attempts."
                )
                self._tripped_circuits.add(process_id)

    async def execute_recovery(
        self,
        process_id: str,
        restart_factory: Callable[[], Coroutine[Any, Any, Any]],
    ) -> bool:
        """Execute automated restart with backoff delay."""
        if not self.can_recover(process_id):
            logger.warning(
                f"Cannot recover process {process_id}: circuit breaker tripped or max attempts exceeded."
            )
            return False

        delay = self.get_backoff_delay(process_id)
        logger.info(
            f"Scheduling restart for process {process_id} after {delay:.1f}s backoff..."
        )
        await asyncio.sleep(delay)

        try:
            await restart_factory()
            self.record_attempt(process_id, success=True)
            logger.info(f"Successfully recovered process {process_id}.")
            return True
        except Exception as ex:
            self.record_attempt(process_id, success=False)
            logger.error(f"Failed recovery attempt for process {process_id}: {ex}")
            return False

    def reset(self, process_id: str) -> None:
        """Reset attempts and clear circuit breaker."""
        self._attempts.pop(process_id, None)
        self._tripped_circuits.discard(process_id)
