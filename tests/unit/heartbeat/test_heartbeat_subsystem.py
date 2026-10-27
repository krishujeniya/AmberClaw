# ruff: noqa: PLR2004
"""Unit tests for Heartbeat isolation, queue, and recovery subsystems."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from amberclaw.heartbeat.engine import HeartbeatStatus
from amberclaw.heartbeat.isolation import ProcessIsolationManager
from amberclaw.heartbeat.queue import (
    HeartbeatPingEvent,
    HeartbeatPriority,
    HeartbeatQueue,
)
from amberclaw.heartbeat.recovery import ProcessRecoveryManager


def test_process_isolation_zombie_detection():
    manager = ProcessIsolationManager(timeout_seconds=5.0)

    now = datetime.now(UTC)
    statuses = {
        "healthy_proc": HeartbeatStatus(
            process_id="healthy_proc",
            is_alive=True,
            last_ping=now,
        ),
        "hung_proc": HeartbeatStatus(
            process_id="hung_proc",
            is_alive=True,
            last_ping=now - timedelta(seconds=10.0),
        ),
    }

    zombies = manager.check_for_zombies(statuses)
    assert zombies == ["hung_proc"]

    # Isolate
    record = manager.isolate_process("hung_proc", reason="Missed SLA")
    assert record.process_id == "hung_proc"
    assert manager.is_isolated("hung_proc") is True

    # Zombie check should now ignore already-isolated processes
    assert manager.check_for_zombies(statuses) == []

    # Release from isolation
    assert manager.release("hung_proc") is True
    assert manager.is_isolated("hung_proc") is False


@pytest.mark.asyncio
async def test_heartbeat_priority_queue():
    queue = HeartbeatQueue(maxsize=10)

    # Put events in reverse priority order
    ev_bg = HeartbeatPingEvent(process_id="p_bg", priority=HeartbeatPriority.BACKGROUND)
    ev_norm = HeartbeatPingEvent(process_id="p_norm", priority=HeartbeatPriority.NORMAL)
    ev_crit = HeartbeatPingEvent(process_id="p_crit", priority=HeartbeatPriority.CRITICAL)

    await queue.put(ev_bg)
    await queue.put(ev_norm)
    await queue.put(ev_crit)

    assert queue.qsize() == 3

    # Must dequeue in priority order: CRITICAL -> NORMAL -> BACKGROUND
    item1 = await queue.get()
    item2 = await queue.get()
    item3 = await queue.get()

    assert item1 is not None and item1.process_id == "p_crit"
    assert item2 is not None and item2.process_id == "p_norm"
    assert item3 is not None and item3.process_id == "p_bg"
    assert queue.empty() is True


@pytest.mark.asyncio
async def test_process_recovery_exponential_backoff_and_circuit_breaker(monkeypatch):
    manager = ProcessRecoveryManager(
        max_attempts=3, base_backoff_seconds=1.0, max_backoff_seconds=10.0
    )

    # 1. Backoff delays
    assert manager.get_backoff_delay("proc_1") == 1.0
    manager.record_attempt("proc_1", success=False)
    assert manager.get_backoff_delay("proc_1") == 2.0
    manager.record_attempt("proc_1", success=False)
    assert manager.get_backoff_delay("proc_1") == 4.0

    # 2. Trip circuit breaker on 3rd failure
    assert manager.can_recover("proc_1") is True
    manager.record_attempt("proc_1", success=False)
    assert manager.can_recover("proc_1") is False

    # Mock sleep to avoid real wait
    async def _mock_sleep(_s):
        return None

    monkeypatch.setattr(asyncio, "sleep", _mock_sleep)

    # Recovery should be rejected when tripped
    async def mock_restart():
        return True

    res = await manager.execute_recovery("proc_1", mock_restart)
    assert res is False

    # Reset circuit breaker
    manager.reset("proc_1")
    assert manager.can_recover("proc_1") is True

    # Successful recovery should reset backoff
    res_ok = await manager.execute_recovery("proc_1", mock_restart)
    assert res_ok is True
    assert manager.get_backoff_delay("proc_1") == 1.0
