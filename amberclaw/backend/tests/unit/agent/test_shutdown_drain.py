"""Shutdown drains owned work before closing tool transports."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from amberclaw.agent.loop import AgentLoop
from amberclaw.agent.subagent import SubagentManager
from amberclaw.bus.events import OutboundMessage


def bare_agent():
    agent = AgentLoop.__new__(AgentLoop)
    agent._closing = False
    agent._running = False
    agent._active_tasks = {}
    agent._consolidation_tasks = set()
    agent._processing_lock = asyncio.Lock()
    agent._plugin_stop_task = None
    agent._mcp_discovery_task = None
    agent._mcp_stack = AsyncMock()
    agent._connect_mcp = AsyncMock()
    agent.plugin_manager = SimpleNamespace(stop=AsyncMock())
    agent.subagents = SimpleNamespace(
        cancel_all=AsyncMock(return_value=0), owns_task=lambda _task: False
    )
    return agent


async def test_shutdown_drains_dispatch_and_consolidation_before_transports():
    agent = bare_agent()
    entered = asyncio.Event()
    finished = set()
    observations = []

    async def work(label):
        entered.set()
        try:
            await asyncio.Future()
        finally:
            finished.add(label)

    agent._track_dispatch("fixture", work("dispatch"))
    consolidation = asyncio.create_task(work("consolidation"))
    agent._consolidation_tasks.add(consolidation)
    await entered.wait()
    await asyncio.sleep(0)
    tasks = [*agent._active_tasks["fixture"], consolidation]

    async def observe():
        observations.append(set(finished))

    agent.plugin_manager.stop.side_effect = observe
    agent._mcp_stack.aclose.side_effect = observe
    try:
        agent.stop()
        await agent.close_mcp()
        assert all(task.done() for task in tasks)
        assert observations == [{"dispatch", "consolidation"}] * 2
        agent.subagents.cancel_all.assert_awaited_once()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def test_shutdown_cancels_active_and_lock_queued_direct_calls():
    agent = bare_agent()
    entered = asyncio.Event()
    attempted = asyncio.Event()
    connects = 0

    async def connect():
        nonlocal connects
        connects += 1
        if connects > 1:
            attempted.set()

    async def process(message, **_kwargs):
        entered.set()
        await asyncio.Future()
        return OutboundMessage(
            channel=message.channel, chat_id=message.chat_id, content="unreachable"
        )

    agent._connect_mcp.side_effect = connect
    agent._process_message = process
    first = asyncio.create_task(agent.process_direct("active"))
    await entered.wait()
    second = asyncio.create_task(agent.process_direct("queued"))
    await attempted.wait()
    try:
        agent.stop()
        await agent.close_mcp()
        await asyncio.sleep(0)
        assert first.done() and second.done()
        with pytest.raises(RuntimeError, match="closing"):
            await agent.process_direct("after shutdown")
    finally:
        first.cancel()
        second.cancel()
        await asyncio.gather(first, second, return_exceptions=True)


async def test_owned_cancellation_finally_can_request_close_without_self_wait():
    agent = bare_agent()
    entered = asyncio.Event()
    left = asyncio.Event()

    async def work():
        entered.set()
        try:
            await asyncio.Future()
        finally:
            await agent.close_mcp()
            left.set()

    agent._track_dispatch("fixture", work())
    await entered.wait()
    try:
        agent.stop()
        await asyncio.wait_for(agent.close_mcp(), timeout=1)
        assert left.is_set()
    finally:
        for task in agent._active_tasks.get("fixture", []):
            task.cancel()


async def test_subagent_cancel_all_drains_maps():
    manager = SubagentManager.__new__(SubagentManager)
    entered = asyncio.Event()

    async def work():
        entered.set()
        await asyncio.Future()

    task = asyncio.create_task(work())
    manager._running_tasks = {"fixture": task}
    manager._session_tasks = {"session": {"fixture"}}
    await entered.wait()
    try:
        assert await manager.cancel_all() == 1
        assert task.cancelled()
        assert manager._running_tasks == {}
        assert manager._session_tasks == {}
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
