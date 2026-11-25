"""Subagent concurrency worker pool and lifecycle manager."""

import asyncio
from collections.abc import Awaitable, Callable

from loguru import logger

from amberclaw.subagent.agent import (
    SubagentResult,
    SubagentStatus,
    SubagentTask,
    SubagentWorker,
)


class SubagentPool:
    """Manages worker concurrency, queuing, status tracking, and resource cleanup for subagents."""

    def __init__(self, max_concurrency: int = 5) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        self.max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._active_workers: dict[str, SubagentWorker] = {}
        self._completed_results: dict[str, SubagentResult] = {}
        self._session_tasks: dict[str, set[str]] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}

    @property
    def active_count(self) -> int:
        """Return the count of actively running or queued workers."""
        return len(self._active_workers)

    @property
    def completed_count(self) -> int:
        """Return the count of completed worker results cached."""
        return len(self._completed_results)

    async def submit(
        self,
        task: SubagentTask,
        runner_fn: Callable[[SubagentTask], Awaitable[str]],
        session_key: str | None = None,
    ) -> str:
        """Submit a SubagentTask to the pool for managed asynchronous execution."""
        worker = SubagentWorker(task)
        task_id = task.task_id
        self._active_workers[task_id] = worker

        if session_key:
            self._session_tasks.setdefault(session_key, set()).add(task_id)

        async def _execute_with_semaphore() -> None:
            async with self._semaphore:
                try:
                    result = await worker.run(runner_fn)
                except asyncio.CancelledError:
                    result = worker.result or SubagentResult(
                        task_id=task_id,
                        status=SubagentStatus.CANCELLED,
                        error="Task was cancelled",
                    )
                finally:
                    self._active_workers.pop(task_id, None)
                    self._completed_results[task_id] = result
                    if session_key and (tids := self._session_tasks.get(session_key)):
                        tids.discard(task_id)
                        if not tids:
                            self._session_tasks.pop(session_key, None)

        bg_task = asyncio.create_task(_execute_with_semaphore())
        self._tasks[task_id] = bg_task
        worker._async_task = bg_task

        logger.debug(
            "Submitted task [{}] to subagent pool (active: {})",
            task_id,
            self.active_count,
        )
        return task_id

    def get_worker(self, task_id: str) -> SubagentWorker | None:
        """Retrieve active worker by task ID."""
        return self._active_workers.get(task_id)

    def get_status(self, task_id: str) -> SubagentStatus | None:
        """Retrieve the execution status of a task."""
        if task_id in self._active_workers:
            return self._active_workers[task_id].status
        if task_id in self._completed_results:
            return self._completed_results[task_id].status
        return None

    def get_result(self, task_id: str) -> SubagentResult | None:
        """Retrieve completed result if finished."""
        return self._completed_results.get(task_id)

    def cancel(self, task_id: str) -> bool:
        """Cancel a single active task by ID."""
        if task_id in self._tasks and not self._tasks[task_id].done():
            self._tasks[task_id].cancel()
            if task_id in self._active_workers:
                self._active_workers[task_id].status = SubagentStatus.CANCELLED
            return True
        return False

    def cancel_session(self, session_key: str) -> int:
        """Cancel all tasks associated with a given session key."""
        task_ids = list(self._session_tasks.get(session_key, []))
        cancelled_count = 0
        for tid in task_ids:
            if self.cancel(tid):
                cancelled_count += 1
        return cancelled_count

    def cancel_all(self) -> int:
        """Cancel all active tasks in the pool."""
        count = 0
        for tid in list(self._tasks.keys()):
            if self.cancel(tid):
                count += 1
        return count

    async def drain(self, timeout: float = 30.0) -> None:
        """Wait for all active tasks to complete or timeout."""
        active = [t for t in self._tasks.values() if not t.done()]
        if not active:
            return
        logger.info(
            "Draining {} active pool tasks (timeout: {}s)", len(active), timeout
        )
        await asyncio.wait(active, timeout=timeout)
