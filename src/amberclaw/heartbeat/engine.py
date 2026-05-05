import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class HeartbeatStatus(BaseModel):
    """
    Represents the health and status of a subagent or system process.
    Uses Pydantic v2 for strict validation.
    """
    process_id: str = Field(..., description="Unique identifier for the process/subagent.")
    is_alive: bool = Field(default=True, description="Whether the process is currently active.")
    last_ping: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary state data.")

class HeartbeatEngine:
    """
    The core OS loop for AmberClaw. 
    Continuously monitors background tasks, subagents, and memory consolidation loops.
    """
    def __init__(self, check_interval_seconds: int = 5):
        self.check_interval_seconds = check_interval_seconds
        self._running = False
        self._tasks: Dict[str, asyncio.Task] = {}
        self._statuses: Dict[str, HeartbeatStatus] = {}

    def register_process(self, process_id: str) -> None:
        """Register a new process to monitor."""
        self._statuses[process_id] = HeartbeatStatus(process_id=process_id)
        logger.info(f"Registered process {process_id} for heartbeat monitoring.")

    def ping(self, process_id: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Update the last_ping timestamp for a process."""
        if process_id in self._statuses:
            self._statuses[process_id].last_ping = datetime.now(timezone.utc)
            self._statuses[process_id].is_alive = True
            if metadata:
                self._statuses[process_id].metadata.update(metadata)

    async def _monitor_loop(self) -> None:
        """Background loop checking for dead processes."""
        while self._running:
            now = datetime.now(timezone.utc)
            for pid, status in self._statuses.items():
                if not status.is_alive:
                    continue
                
                # If a process hasn't pinged in 3x the check interval, mark it dead
                time_since_ping = (now - status.last_ping).total_seconds()
                if time_since_ping > (self.check_interval_seconds * 3):
                    logger.warning(f"Process {pid} missed heartbeat! Marking as dead.")
                    status.is_alive = False
                    # Here we would trigger recovery protocols (Option A focus)

            await asyncio.sleep(self.check_interval_seconds)

    async def start(self) -> None:
        """Start the heartbeat engine."""
        if self._running:
            return
        
        self._running = True
        self._tasks["monitor"] = asyncio.create_task(self._monitor_loop())
        logger.info("Heartbeat Engine started.")

    async def stop(self) -> None:
        """Stop the heartbeat engine safely."""
        self._running = False
        for task in self._tasks.values():
            task.cancel()
        
        # Wait for tasks to gracefully exit
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        logger.info("Heartbeat Engine stopped.")
