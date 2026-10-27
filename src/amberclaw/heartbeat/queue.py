"""Priority-aware heartbeat event queue for agent process monitoring."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from enum import IntEnum
from typing import Any

from pydantic import BaseModel, Field


class HeartbeatPriority(IntEnum):
    """Priority levels for heartbeat queue items (lower number = higher priority)."""

    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    BACKGROUND = 3


class HeartbeatPingEvent(BaseModel):
    """Heartbeat signal sent from a monitored process."""

    process_id: str
    priority: HeartbeatPriority = HeartbeatPriority.NORMAL
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    def __lt__(self, other: HeartbeatPingEvent) -> bool:
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp


class HeartbeatQueue:
    """Bounded, priority-aware queue for heartbeat events."""

    def __init__(self, maxsize: int = 1000) -> None:
        self.maxsize = maxsize
        self._queue: asyncio.PriorityQueue[tuple[int, HeartbeatPingEvent]] = (
            asyncio.PriorityQueue(maxsize=maxsize)
        )

    async def put(
        self,
        event: HeartbeatPingEvent,
        timeout: float | None = 2.0,
    ) -> bool:
        """Enqueue a heartbeat event with timeout."""
        try:
            item = (int(event.priority), event)
            if timeout is not None:
                await asyncio.wait_for(self._queue.put(item), timeout=timeout)
            else:
                await self._queue.put(item)
            return True
        except TimeoutError:
            return False

    async def get(
        self,
        timeout: float | None = None,
    ) -> HeartbeatPingEvent | None:
        """Dequeue highest priority heartbeat event."""
        try:
            if timeout is not None:
                _, event = await asyncio.wait_for(self._queue.get(), timeout=timeout)
            else:
                _, event = await self._queue.get()
            return event
        except TimeoutError:
            return None

    def qsize(self) -> int:
        """Return current queue depth."""
        return self._queue.qsize()

    def empty(self) -> bool:
        """Check if queue is empty."""
        return self._queue.empty()
