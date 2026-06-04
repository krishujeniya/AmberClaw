import asyncio
import contextlib
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from amberclaw.agent.loop import AgentLoop
from amberclaw.bus.events import InboundMessage
from amberclaw.bus.queue import MessageBus
from amberclaw.core.kernel import ClawOSSupervisor


@pytest.mark.asyncio
async def test_supervisor_registration_and_lifecycle(tmp_path: Path):
    bus = MessageBus()
    supervisor = ClawOSSupervisor(bus=bus, workspace=tmp_path, check_interval_s=0.1)

    start_called = asyncio.Event()
    stop_called = asyncio.Event()

    async def mock_start():
        start_called.set()
        # Keep running
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.sleep(10)

    def mock_stop():
        stop_called.set()

    supervisor.register_service("test_service", mock_start, mock_stop)

    # Start
    await supervisor.start()
    await asyncio.sleep(0.05)
    assert start_called.is_set()
    assert supervisor._services["test_service"]["status"] == "running"

    # Stop
    await supervisor.stop()
    await asyncio.sleep(0.05)
    assert stop_called.is_set()
    assert supervisor._services["test_service"]["status"] == "stopped"


@pytest.mark.asyncio
async def test_supervisor_auto_recovery(tmp_path: Path):
    bus = MessageBus()
    # Low check interval for fast test execution
    supervisor = ClawOSSupervisor(bus=bus, workspace=tmp_path, check_interval_s=0.05)

    crash_event = asyncio.Event()
    start_count = 0

    async def mock_start():
        nonlocal start_count
        start_count += 1
        if start_count == 1:
            # First run: exit immediately (crash)
            return
        # Second run: keep running
        await crash_event.wait()

    def mock_stop():
        pass

    supervisor.register_service("unstable_service", mock_start, mock_stop)

    await supervisor.start()

    # Wait a bit for the supervisor loop to detect the exit and restart
    await asyncio.sleep(0.2)

    assert start_count > 1
    assert supervisor._services["unstable_service"]["status"] == "running"

    crash_event.set()
    await supervisor.stop()


@pytest.mark.asyncio
async def test_supervisor_health_monitor_diagnostics(tmp_path: Path):
    bus = MessageBus()
    nonexistent_path = tmp_path / "nonexistent_amberclaw_path"
    supervisor = ClawOSSupervisor(
        bus=bus, workspace=nonexistent_path, check_interval_s=0.05,
    )

    # With no API keys in environment and non-existent workspace,
    # run_diagnostics should publish critical workspace_invalid and
    # api_key_missing events
    with patch.dict(os.environ, {}, clear=True):
        await supervisor.run_diagnostics()

    events = []
    while bus.system_events_size > 0:
        events.append(await bus.consume_system_event())

    expected_min_events = 2
    assert len(events) >= expected_min_events
    types = [e.event_type for e in events]
    assert "workspace_invalid" in types
    assert "api_key_missing" in types


@pytest.mark.asyncio
async def test_agent_loop_low_memory_reaction(tmp_path: Path):
    bus = MessageBus()

    # Mock LLM provider, session manager, and sessions list
    mock_provider = MagicMock()
    mock_sessions = MagicMock()

    mock_session_info = {"key": "cli:test_session"}
    mock_sessions.list_sessions.return_value = [mock_session_info]

    mock_session = MagicMock()
    mock_sessions.get_session.return_value = mock_session

    agent = AgentLoop(
        bus=bus,
        provider=mock_provider,
        workspace=tmp_path,
        session_manager=mock_sessions,
    )

    # Stub connect_mcp and consolidate_memory
    agent._connect_mcp = AsyncMock()
    agent._consolidate_memory = AsyncMock()

    # Create a low memory event message
    low_mem_msg = InboundMessage(
        channel="system",
        sender_id="supervisor",
        chat_id="system",
        content="Low memory alert",
        metadata={"system_event_type": "low_memory"},
    )

    # Put it on the inbound queue
    await bus.publish_inbound(low_mem_msg)

    # Start loop in a task
    loop_task = asyncio.create_task(agent.run())

    # Wait for queue to empty or consolidation to run
    await asyncio.sleep(0.15)

    # Stop the agent loop
    agent.stop()
    await loop_task

    # Verify that memory consolidation was triggered on the active session
    agent._consolidate_memory.assert_called_once_with(mock_session, archive_all=True)
