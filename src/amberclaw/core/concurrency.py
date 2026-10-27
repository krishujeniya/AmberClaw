"""Structured concurrency, task groups, deadlines, and controlled non-blocking execution.

Implements Section 13 Async Correctness:
- StructuredTaskGroup for robust parent-child lifecycle and cancellation propagation.
- DeadlineContext for end-to-end deadline budgeting across provider, tool, and storage calls.
- ControlledThreadPool for offloading blocking SQLite, filesystem, and subprocess I/O.
- TaskRegistry to prevent leaked unawaited tasks and facilitate clean shutdown draining.
"""

import asyncio
import functools
import time
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractAsyncContextManager
from typing import Any, TypeVar

from loguru import logger

T = TypeVar("T")


class StructuredTaskGroup(AbstractAsyncContextManager):
    """Structured concurrency context manager with eager sibling cancellation on failure."""

    def __init__(self, name: str = "task_group") -> None:
        self.name = name
        self._tg: asyncio.TaskGroup | None = None
        self._tasks: list[asyncio.Task[Any]] = []

    async def __aenter__(self) -> "StructuredTaskGroup":
        self._tg = asyncio.TaskGroup()
        await self._tg.__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool | None:
        if self._tg:
            try:
                return await self._tg.__aexit__(exc_type, exc_val, exc_tb)
            except* Exception as eg:
                logger.error(
                    "StructuredTaskGroup '{}' captured task group exception: {}",
                    self.name,
                    eg,
                )
                raise
        return None

    def create_task(
        self, coro: Awaitable[T], name: str | None = None
    ) -> asyncio.Task[T]:
        """Spawn a child task bound to this structured task group."""
        if not self._tg:
            raise RuntimeError(
                "StructuredTaskGroup is not active. Use within 'async with'."
            )
        task_name = f"{self.name}:{name or 'child'}"
        task = self._tg.create_task(coro, name=task_name)
        self._tasks.append(task)
        return task

    @property
    def tasks(self) -> list[asyncio.Task[Any]]:
        return list(self._tasks)


class DeadlineContext:
    """Propagates and bounds execution deadlines across asynchronous subroutines."""

    def __init__(self, timeout_sec: float) -> None:
        self.timeout_sec = max(0.001, timeout_sec)
        self.start_time: float = 0.0
        self.end_time: float = 0.0

    def __enter__(self) -> "DeadlineContext":
        self.start_time = time.monotonic()
        self.end_time = self.start_time + self.timeout_sec
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    def remaining(self) -> float:
        """Remaining duration in seconds before the deadline expires."""
        if self.start_time == 0.0:
            return self.timeout_sec
        rem = self.end_time - time.monotonic()
        return max(0.0, rem)

    def is_expired(self) -> bool:
        """Check if deadline has passed."""
        return self.remaining() <= 0.0

    async def run(self, coro: Awaitable[T]) -> T:
        """Execute a coroutine within the remaining deadline budget."""
        rem = self.remaining()
        if rem <= 0.0:
            raise TimeoutError("Deadline expired before execution could begin")
        return await asyncio.wait_for(coro, timeout=rem)


class ControlledThreadPool:
    """Dedicated thread pool for offloading synchronous I/O without blocking event loop."""

    _instance: "ControlledThreadPool | None" = None

    def __init__(self, max_workers: int = 16) -> None:
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="amberclaw-async-worker",
        )

    @classmethod
    def get_instance(cls) -> "ControlledThreadPool":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def run_sync(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Run blocking function in the controlled worker pool."""
        loop = asyncio.get_running_loop()
        call = functools.partial(func, *args, **kwargs)
        return await loop.run_in_executor(self.executor, call)

    def shutdown(self, wait: bool = True) -> None:
        self.executor.shutdown(wait=wait)


class TaskRegistry:
    """Registry tracking active background tasks to detect leaks and coordinate graceful drains."""

    _instance: "TaskRegistry | None" = None

    def __init__(self) -> None:
        self._tasks: dict[asyncio.Task[Any], str] = {}

    @classmethod
    def get_instance(cls) -> "TaskRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, task: asyncio.Task[Any], name: str = "unnamed_task") -> None:
        """Register a background task."""
        self._tasks[task] = name
        task.add_done_callback(lambda t: self._tasks.pop(t, None))

    def active_tasks(self) -> list[tuple[asyncio.Task[Any], str]]:
        """Return currently running uncompleted tasks."""
        return [(t, name) for t, name in self._tasks.items() if not t.done()]

    def count(self) -> int:
        return len(self.active_tasks())

    async def drain(self, timeout: float = 5.0) -> None:
        """Cancel and await all registered background tasks within a timeout."""
        running = [t for t, _ in self.active_tasks()]
        if not running:
            return

        for t in running:
            t.cancel()

        try:
            await asyncio.wait_for(
                asyncio.gather(*running, return_exceptions=True),
                timeout=timeout,
            )
        except TimeoutError:
            logger.warning("TaskRegistry: drain exceeded {}s timeout", timeout)
        finally:
            self._tasks.clear()

    def clear(self) -> None:
        self._tasks.clear()
