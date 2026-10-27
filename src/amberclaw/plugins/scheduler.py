"""Plugin execution scheduler for recurring background jobs and automated health probes."""

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


class PluginScheduledTask(BaseModel):
    """Specification of a recurring plugin tool execution job."""

    task_id: str = Field(default_factory=lambda: f"PLG-JOB-{uuid.uuid4().hex[:8]}")
    plugin_name: str = Field(..., description="Target plugin identifier")
    tool_name: str = Field(..., description="Name of registered tool to execute")
    interval_seconds: float = Field(
        ..., ge=1.0, description="Repetition period in seconds"
    )
    arguments: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = Field(default=True)
    last_run: float | None = None
    run_count: int = Field(default=0, ge=0)


class PluginScheduler:
    """Coordinates periodic execution cycles for installed plugins and registered tools."""

    def __init__(self) -> None:
        self._tasks: dict[str, PluginScheduledTask] = {}
        self._running = False
        self._runner_task: asyncio.Task[None] | None = None

    def schedule_task(
        self,
        plugin_name: str,
        tool_name: str,
        interval_seconds: float,
        arguments: dict[str, Any] | None = None,
    ) -> PluginScheduledTask:
        """Register a periodic execution task for a plugin tool."""
        task = PluginScheduledTask(
            plugin_name=plugin_name,
            tool_name=tool_name,
            interval_seconds=interval_seconds,
            arguments=arguments or {},
        )
        self._tasks[task.task_id] = task
        logger.info(
            "Scheduled plugin task [{}] for '{}.{}' every {:.1f}s",
            task.task_id,
            plugin_name,
            tool_name,
            interval_seconds,
        )
        return task

    def cancel_task(self, task_id: str) -> bool:
        """Cancel and remove a scheduled plugin task."""
        if task_id in self._tasks:
            self._tasks[task_id].is_active = False
            del self._tasks[task_id]
            logger.info("Cancelled plugin scheduled task [{}]", task_id)
            return True
        return False

    def get_task(self, task_id: str) -> PluginScheduledTask | None:
        """Retrieve scheduled task by ID."""
        return self._tasks.get(task_id)

    def list_tasks(self, active_only: bool = True) -> list[PluginScheduledTask]:
        """Return list of scheduled plugin tasks."""
        if active_only:
            return [t for t in self._tasks.values() if t.is_active]
        return list(self._tasks.values())

    async def run_due_tasks(
        self,
        invoker_fn: Callable[[str, str, dict[str, Any]], Awaitable[Any]],
    ) -> list[dict[str, Any]]:
        """Evaluate all scheduled tasks and execute those whose interval has elapsed."""
        now = time.time()
        results: list[dict[str, Any]] = []

        for task in list(self._tasks.values()):
            if not task.is_active:
                continue

            time_since_last = now - (task.last_run or 0.0)
            if task.last_run is None or time_since_last >= task.interval_seconds:
                try:
                    logger.debug(
                        "Executing scheduled plugin task [{}]: {}.{}",
                        task.task_id,
                        task.plugin_name,
                        task.tool_name,
                    )
                    res = await invoker_fn(
                        task.plugin_name, task.tool_name, task.arguments
                    )
                    task.last_run = now
                    task.run_count += 1
                    results.append(
                        {"task_id": task.task_id, "status": "ok", "result": res}
                    )
                except Exception as exc:
                    logger.error(
                        "Failed scheduled execution of task [{}]: {}", task.task_id, exc
                    )
                    task.last_run = now
                    task.run_count += 1
                    results.append(
                        {"task_id": task.task_id, "status": "error", "error": str(exc)}
                    )

        return results

    def clear(self) -> None:
        """Clear all scheduled tasks."""
        self._tasks.clear()
