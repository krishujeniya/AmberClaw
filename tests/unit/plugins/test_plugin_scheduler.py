# ruff: noqa: PLR2004
"""Unit tests for the amberclaw.plugins.scheduler module."""

import pytest

from amberclaw.plugins.scheduler import PluginScheduler


@pytest.mark.asyncio
async def test_plugin_scheduler_lifecycle():
    scheduler = PluginScheduler()

    task = scheduler.schedule_task(
        plugin_name="weather",
        tool_name="get_current_temp",
        interval_seconds=10.0,
        arguments={"city": "San Francisco"},
    )
    assert task.task_id.startswith("PLG-JOB-")
    assert task.interval_seconds == 10.0
    assert scheduler.get_task(task.task_id) is not None

    invoked_calls = []

    async def _mock_invoker(plugin: str, tool: str, args: dict) -> str:
        invoked_calls.append((plugin, tool, args))
        return f"{plugin}.{tool} executed"

    # First run executes because last_run is None
    results = await scheduler.run_due_tasks(_mock_invoker)
    assert len(results) == 1
    assert results[0]["status"] == "ok"
    assert len(invoked_calls) == 1
    assert task.run_count == 1

    # Second immediate run should NOT execute because interval (10s) hasn't elapsed
    results2 = await scheduler.run_due_tasks(_mock_invoker)
    assert len(results2) == 0

    # Cancel task
    assert scheduler.cancel_task(task.task_id) is True
    assert scheduler.get_task(task.task_id) is None
    assert len(scheduler.list_tasks()) == 0
