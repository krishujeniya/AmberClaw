"""Subagent worker execution primitives, task specifications, and execution results."""

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


class SubagentStatus(StrEnum):
    """Lifecycle states of a subagent execution task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class SubagentTask(BaseModel):
    """Specification of work assigned to an isolated subagent worker."""

    task_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    task: str = Field(..., description="The objective or instruction to execute")
    label: str | None = Field(
        default=None, description="Human-readable label or description"
    )
    role: str = Field(
        default="general",
        description="Worker role specialization (coder, researcher, etc.)",
    )
    origin: dict[str, str] = Field(
        default_factory=dict,
        description="Routing metadata for result delivery (e.g., channel, chat_id)",
    )
    timeout_seconds: float = Field(
        default=300.0, ge=0.01, description="Maximum execution duration"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary task context"
    )
    created_at: float = Field(
        default_factory=time.time, description="Creation unix timestamp"
    )


class SubagentResult(BaseModel):
    """Structured outcome of a subagent worker execution."""

    task_id: str
    status: SubagentStatus
    output: str | None = None
    error: str | None = None
    execution_time_seconds: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class SubagentWorker:
    """Manages the lifecycle and execution of a single SubagentTask."""

    def __init__(self, task: SubagentTask) -> None:
        self.task = task
        self.status = SubagentStatus.PENDING
        self.result: SubagentResult | None = None
        self._async_task: asyncio.Task[SubagentResult] | None = None

    async def run(
        self,
        runner_fn: Callable[[SubagentTask], Awaitable[str]],
    ) -> SubagentResult:
        """Execute the subagent task using the provided async runner with timeout enforcement."""
        self.status = SubagentStatus.RUNNING
        start_time = time.time()
        logger.info(
            "SubagentWorker [{}] started task '{}' (role: {})",
            self.task.task_id,
            self.task.label or self.task.task[:30],
            self.task.role,
        )

        try:
            output = await asyncio.wait_for(
                runner_fn(self.task),
                timeout=self.task.timeout_seconds,
            )
            elapsed = time.time() - start_time
            self.status = SubagentStatus.COMPLETED
            self.result = SubagentResult(
                task_id=self.task.task_id,
                status=SubagentStatus.COMPLETED,
                output=output,
                execution_time_seconds=elapsed,
                metadata=self.task.metadata,
            )
            logger.info(
                "SubagentWorker [{}] completed in {:.2f}s", self.task.task_id, elapsed
            )
        except TimeoutError:
            elapsed = time.time() - start_time
            self.status = SubagentStatus.TIMEOUT
            self.result = SubagentResult(
                task_id=self.task.task_id,
                status=SubagentStatus.TIMEOUT,
                error=f"Task timed out after {self.task.timeout_seconds} seconds",
                execution_time_seconds=elapsed,
                metadata=self.task.metadata,
            )
            logger.warning(
                "SubagentWorker [{}] timed out after {:.2f}s",
                self.task.task_id,
                elapsed,
            )
        except asyncio.CancelledError:
            elapsed = time.time() - start_time
            self.status = SubagentStatus.CANCELLED
            self.result = SubagentResult(
                task_id=self.task.task_id,
                status=SubagentStatus.CANCELLED,
                error="Task execution was cancelled",
                execution_time_seconds=elapsed,
                metadata=self.task.metadata,
            )
            logger.info(
                "SubagentWorker [{}] cancelled after {:.2f}s",
                self.task.task_id,
                elapsed,
            )
            raise
        except Exception as exc:
            elapsed = time.time() - start_time
            self.status = SubagentStatus.FAILED
            self.result = SubagentResult(
                task_id=self.task.task_id,
                status=SubagentStatus.FAILED,
                error=str(exc),
                execution_time_seconds=elapsed,
                metadata=self.task.metadata,
            )
            logger.error(
                "SubagentWorker [{}] failed after {:.2f}s: {}",
                self.task.task_id,
                elapsed,
                exc,
            )

        return self.result

    def cancel(self) -> bool:
        """Attempt to cancel active execution."""
        if self._async_task and not self._async_task.done():
            self._async_task.cancel()
            self.status = SubagentStatus.CANCELLED
            return True
        return False
