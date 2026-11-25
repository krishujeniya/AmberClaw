# ruff: noqa: PLR2004
"""Unit tests for the amberclaw.subagent package (workers, isolation, pool, RPC)."""

import asyncio
from pathlib import Path

import pytest

from amberclaw.subagent.agent import (
    SubagentStatus,
    SubagentTask,
    SubagentWorker,
)
from amberclaw.subagent.isolation import (
    IsolationPolicy,
    SubagentIsolationContext,
)
from amberclaw.subagent.pool import SubagentPool
from amberclaw.subagent.rpc import (
    RPCMessage,
    RPCMessageType,
    SubagentRPCChannel,
)

# ==============================================================================
# Worker & Task Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_subagent_worker_success():
    task = SubagentTask(task="echo test", timeout_seconds=5.0)
    worker = SubagentWorker(task)

    async def _mock_run(t: SubagentTask) -> str:
        return f"Completed: {t.task}"

    result = await worker.run(_mock_run)
    assert result.status == SubagentStatus.COMPLETED
    assert result.output == "Completed: echo test"
    assert result.error is None
    assert result.execution_time_seconds >= 0.0


@pytest.mark.asyncio
async def test_subagent_worker_timeout():
    task = SubagentTask(task="sleep long", timeout_seconds=0.05)
    worker = SubagentWorker(task)

    async def _mock_slow_run(_t: SubagentTask) -> str:
        await asyncio.sleep(0.5)
        return "done"

    result = await worker.run(_mock_slow_run)
    assert result.status == SubagentStatus.TIMEOUT
    assert "timed out" in (result.error or "")
    assert result.output is None


@pytest.mark.asyncio
async def test_subagent_worker_failure():
    task = SubagentTask(task="failing task", timeout_seconds=5.0)
    worker = SubagentWorker(task)

    async def _mock_fail(_t: SubagentTask) -> str:
        raise ValueError("Simulated execution failure")

    result = await worker.run(_mock_fail)
    assert result.status == SubagentStatus.FAILED
    assert "Simulated execution failure" in (result.error or "")


# ==============================================================================
# Isolation & Containment Tests
# ==============================================================================


def test_isolation_path_containment(tmp_path: Path):
    workspace = tmp_path / "sandbox"
    workspace.mkdir()
    allowed_dir = tmp_path / "shared"
    allowed_dir.mkdir()
    outside_dir = tmp_path / "forbidden"
    outside_dir.mkdir()

    policy = IsolationPolicy(
        workspace_root=workspace,
        allowed_paths=[allowed_dir],
        read_only=False,
    )
    ctx = SubagentIsolationContext(policy)

    valid_file = workspace / "test.txt"
    assert ctx.is_path_allowed(valid_file)
    assert ctx.validate_path(valid_file) == valid_file.resolve()

    shared_file = allowed_dir / "data.csv"
    assert ctx.is_path_allowed(shared_file)

    forbidden_file = outside_dir / "secret.key"
    assert not ctx.is_path_allowed(forbidden_file)
    with pytest.raises(PermissionError):
        ctx.validate_path(forbidden_file)


def test_isolation_read_only_mode(tmp_path: Path):
    workspace = tmp_path / "readonly_sandbox"
    workspace.mkdir()

    policy = IsolationPolicy(workspace_root=workspace, read_only=True)
    ctx = SubagentIsolationContext(policy)

    target_file = workspace / "data.json"
    assert ctx.is_path_allowed(target_file, write=False)
    assert not ctx.is_path_allowed(target_file, write=True)

    with pytest.raises(PermissionError):
        ctx.validate_path(target_file, write=True)


def test_isolation_environment_sanitizer(tmp_path: Path):
    policy = IsolationPolicy(
        workspace_root=tmp_path,
        env_allowlist=["PATH", "LANG"],
    )
    ctx = SubagentIsolationContext(policy)

    raw_env = {
        "PATH": "/usr/bin:/bin",
        "LANG": "en_US.UTF-8",
        "OPENAI_API_KEY": "sk-secret-12345",
        "AWS_SECRET_ACCESS_KEY": "supersecret",
    }
    sanitized = ctx.sanitize_environment(raw_env)
    assert "PATH" in sanitized
    assert "LANG" in sanitized
    assert "OPENAI_API_KEY" not in sanitized
    assert "AWS_SECRET_ACCESS_KEY" not in sanitized


def test_isolation_memory_check(tmp_path: Path):
    policy = IsolationPolicy(workspace_root=tmp_path, max_memory_mb=256)
    ctx = SubagentIsolationContext(policy)

    assert ctx.check_memory(128.0) is True
    assert ctx.check_memory(256.0) is True
    assert ctx.check_memory(256.1) is False


# ==============================================================================
# RPC Channel Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_rpc_channel_notify_and_history():
    channel = SubagentRPCChannel()
    received_messages: list[RPCMessage] = []

    async def _worker_b_handler(msg: RPCMessage) -> None:
        received_messages.append(msg)

    channel.register_handler("worker-b", _worker_b_handler)

    sent = await channel.notify(
        source_id="worker-a",
        target_id="worker-b",
        payload={"task_update": "done"},
    )
    assert sent.source_id == "worker-a"
    assert sent.target_id == "worker-b"

    # Give event loop a cycle to dispatch
    await asyncio.sleep(0.02)
    assert len(received_messages) == 1
    assert received_messages[0].payload == {"task_update": "done"}

    history = channel.get_history()
    assert len(history) >= 1
    assert history[-1].payload == {"task_update": "done"}


@pytest.mark.asyncio
async def test_rpc_channel_call_and_respond():
    channel = SubagentRPCChannel()

    async def _calc_handler(msg: RPCMessage) -> dict:
        if msg.method == "add":
            a = msg.payload.get("a", 0)
            b = msg.payload.get("b", 0)
            return {"result": a + b}
        return {"error": "unknown method"}

    channel.register_handler("math-service", _calc_handler)

    response = await channel.call(
        source_id="requester",
        target_id="math-service",
        method="add",
        params={"a": 15, "b": 27},
        timeout=2.0,
    )
    assert response == {"result": 42}


@pytest.mark.asyncio
async def test_rpc_channel_call_target_not_found():
    channel = SubagentRPCChannel()
    with pytest.raises(ConnectionError, match="No active RPC handler"):
        await channel.call(
            source_id="worker",
            target_id="non-existent",
            method="test",
            params={},
            timeout=1.0,
        )


@pytest.mark.asyncio
async def test_rpc_channel_progress():
    channel = SubagentRPCChannel()
    progress_received: list[dict] = []

    async def _main_handler(msg: RPCMessage) -> None:
        if msg.msg_type == RPCMessageType.PROGRESS:
            progress_received.append(msg.payload)

    channel.register_handler("main-agent", _main_handler)
    await channel.send_progress("subagent-1", "main-agent", 50.0, "Halfway done")
    await asyncio.sleep(0.02)

    assert len(progress_received) == 1
    assert progress_received[0]["progress"] == 50.0
    assert progress_received[0]["message"] == "Halfway done"


# ==============================================================================
# Subagent Pool Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_subagent_pool_concurrency_and_submit():
    pool = SubagentPool(max_concurrency=2)
    assert pool.max_concurrency == 2
    assert pool.active_count == 0

    async def _dummy_runner(t: SubagentTask) -> str:
        await asyncio.sleep(0.05)
        return f"Output of {t.task}"

    task1 = SubagentTask(task="Job 1")
    task2 = SubagentTask(task="Job 2")
    task3 = SubagentTask(task="Job 3")

    tid1 = await pool.submit(task1, _dummy_runner, session_key="session-x")
    tid2 = await pool.submit(task2, _dummy_runner, session_key="session-x")
    tid3 = await pool.submit(task3, _dummy_runner, session_key="session-y")

    assert pool.active_count > 0

    await pool.drain(timeout=2.0)
    assert pool.active_count == 0

    res1 = pool.get_result(tid1)
    res2 = pool.get_result(tid2)
    res3 = pool.get_result(tid3)

    assert res1 is not None and res1.status == SubagentStatus.COMPLETED
    assert res2 is not None and res2.status == SubagentStatus.COMPLETED
    assert res3 is not None and res3.status == SubagentStatus.COMPLETED
    assert pool.completed_count == 3


@pytest.mark.asyncio
async def test_subagent_pool_cancel_by_session():
    pool = SubagentPool(max_concurrency=4)

    async def _never_ending(_t: SubagentTask) -> str:
        await asyncio.sleep(100.0)
        return "done"

    t1 = SubagentTask(task="Long 1")
    t2 = SubagentTask(task="Long 2")
    t3 = SubagentTask(task="Other Session")

    await pool.submit(t1, _never_ending, session_key="target-session")
    await pool.submit(t2, _never_ending, session_key="target-session")
    tid3 = await pool.submit(t3, _never_ending, session_key="other-session")

    assert pool.active_count == 3
    cancelled = pool.cancel_session("target-session")
    assert cancelled == 2

    # Allow cancellation propagation
    await asyncio.sleep(0.05)
    assert pool.get_status(t1.task_id) == SubagentStatus.CANCELLED
    assert pool.get_status(t2.task_id) == SubagentStatus.CANCELLED

    # Clean up other task
    pool.cancel(tid3)
