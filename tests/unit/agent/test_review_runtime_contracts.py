"""Cleanup and shared processing contracts found during integration review."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from amberclaw.agent.loop import AgentLoop
from amberclaw.bus.events import InboundMessage, OutboundMessage


def _make_runtime():
    agent = AgentLoop.__new__(AgentLoop)
    agent._active_tasks = {}
    agent._consolidation_tasks = set()
    agent._closing = False
    agent.subagents = SimpleNamespace(
        cancel_all=AsyncMock(return_value=0), owns_task=lambda _task: False
    )
    agent.plugin_manager = SimpleNamespace(stop=AsyncMock())
    return agent


async def test_failed_discovery_still_closes_mcp_stack():
    agent = _make_runtime()
    agent._mcp_stack = AsyncMock()
    stack = agent._mcp_stack
    agent._plugin_stop_task = None

    async def fail():
        raise OSError("discovery failed")

    agent._mcp_discovery_task = asyncio.create_task(fail())
    await asyncio.sleep(0)
    with pytest.raises(OSError, match="discovery failed"):
        await agent.close_mcp()
    stack.aclose.assert_awaited_once()
    assert agent._mcp_stack is None


async def test_direct_calls_share_the_bus_processing_lock():
    agent = _make_runtime()
    agent._processing_lock = asyncio.Lock()
    direct_attempted = asyncio.Event()
    agent._connect_mcp = AsyncMock(side_effect=direct_attempted.set)
    agent.bus = AsyncMock()
    entered = asyncio.Event()
    release = asyncio.Event()
    order = []

    async def process(message, **_kwargs):
        order.append(message.content)
        if message.content == "bus":
            entered.set()
            await release.wait()
        return OutboundMessage(
            channel=message.channel, chat_id=message.chat_id, content="done"
        )

    agent._process_message = process
    bus_task = asyncio.create_task(
        agent._dispatch(
            InboundMessage(
                channel="cli", chat_id="bus", sender_id="fixture", content="bus"
            )
        )
    )
    await entered.wait()
    direct = asyncio.create_task(agent.process_direct("direct"))
    try:
        await direct_attempted.wait()
        assert order == ["bus"]
    finally:
        release.set()
        await asyncio.gather(bus_task, direct)
    assert order == ["bus", "direct"]
