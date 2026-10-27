# ruff: noqa: PLR2004
"""Unit tests for Section 13: Async Correctness, Structured Concurrency, and Deadlines."""

import asyncio
import contextlib
import time

import pytest

from amberclaw.core.concurrency import (
    ControlledThreadPool,
    DeadlineContext,
    StructuredTaskGroup,
    TaskRegistry,
)


@pytest.fixture(autouse=True)
def clean_registry():
    TaskRegistry.get_instance().clear()
    yield
    TaskRegistry.get_instance().clear()


# ==============================================================================
# 1. Structured Task Group & Cancellation Propagation
# ==============================================================================


@pytest.mark.asyncio
async def test_structured_task_group_concurrent_execution():
    results: list[int] = []

    async def worker(val: int):
        await asyncio.sleep(0.01)
        results.append(val)

    async with StructuredTaskGroup("test_group") as tg:
        tg.create_task(worker(1), name="w1")
        tg.create_task(worker(2), name="w2")
        tg.create_task(worker(3), name="w3")

    assert sorted(results) == [1, 2, 3]


@pytest.mark.asyncio
async def test_structured_task_group_eager_cancellation_on_failure():
    sibling_cancelled = False

    async def failing_worker():
        await asyncio.sleep(0.01)
        raise ValueError("Simulated task failure")

    async def slow_sibling():
        nonlocal sibling_cancelled
        try:
            await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            sibling_cancelled = True
            raise

    with pytest.raises(ExceptionGroup) as exc_info:
        async with StructuredTaskGroup("failure_group") as tg:
            tg.create_task(failing_worker(), name="failer")
            tg.create_task(slow_sibling(), name="sibling")

    assert any("Simulated task failure" in str(e) for e in exc_info.value.exceptions)
    assert sibling_cancelled is True


# ==============================================================================
# 2. Deadline Context & Budgeting
# ==============================================================================


@pytest.mark.asyncio
async def test_deadline_context_bounds_execution():
    with DeadlineContext(timeout_sec=0.05) as dl:
        assert dl.remaining() > 0.0
        assert dl.is_expired() is False

        # Fast task succeeds
        async def fast_op():
            await asyncio.sleep(0.01)
            return "ok"

        res = await dl.run(fast_op())
        assert res == "ok"

        # Slow task exceeding deadline raises TimeoutError
        async def slow_op():
            await asyncio.sleep(0.2)

        with pytest.raises(TimeoutError):
            await dl.run(slow_op())

        assert dl.is_expired() is True


@pytest.mark.asyncio
async def test_expired_deadline_aborts_immediately():
    dl = DeadlineContext(timeout_sec=0.01)
    with dl:
        await asyncio.sleep(0.02)
        assert dl.is_expired() is True

        async def quick_op():
            return "done"

        coro = quick_op()
        with pytest.raises(TimeoutError) as exc_info:
            await dl.run(coro)
        coro.close()
        assert "Deadline expired" in str(exc_info.value)


# ==============================================================================
# 3. Controlled Thread Pool (Non-Blocking Sync Execution)
# ==============================================================================


@pytest.mark.asyncio
async def test_controlled_thread_pool_sync_execution():
    pool = ControlledThreadPool.get_instance()

    def sync_blocking_io(num: int) -> int:
        time.sleep(0.02)
        return num * 2

    start = time.monotonic()
    # Run 3 sync tasks concurrently via thread pool
    t1 = pool.run_sync(sync_blocking_io, 10)
    t2 = pool.run_sync(sync_blocking_io, 20)
    t3 = pool.run_sync(sync_blocking_io, 30)

    res = await asyncio.gather(t1, t2, t3)
    duration = time.monotonic() - start

    assert res == [20, 40, 60]
    # If they were blocking the loop sequentially, it would take >=0.06s.
    # In thread pool, they run concurrently in ~0.02-0.04s.
    assert duration < 0.15


# ==============================================================================
# 4. Task Registry & Clean Drain
# ==============================================================================


@pytest.mark.asyncio
async def test_task_registry_leak_tracking_and_drain():
    registry = TaskRegistry.get_instance()

    async def long_running_worker():
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.sleep(10.0)

    t1 = asyncio.create_task(long_running_worker())
    t2 = asyncio.create_task(long_running_worker())

    registry.register(t1, name="bg_1")
    registry.register(t2, name="bg_2")

    assert registry.count() == 2

    # Clean drain cancels and drains all active tasks
    await registry.drain(timeout=0.5)

    assert registry.count() == 0
    assert t1.cancelled() or t1.done()
    assert t2.cancelled() or t2.done()


# ==============================================================================
# 5. Concurrency Stress Test
# ==============================================================================


@pytest.mark.asyncio
async def test_concurrency_stress_100_workers():
    """Verify system stability under 100 concurrent workers updating shared state."""
    counter = 0
    lock = asyncio.Lock()

    async def worker():
        nonlocal counter
        async with lock:
            current = counter
            await asyncio.sleep(0.0001)
            counter = current + 1

    async with StructuredTaskGroup("stress_group") as tg:
        for i in range(100):
            tg.create_task(worker(), name=f"worker_{i}")

    assert counter == 100
