"""Plugin shutdown remains owned until close, including MCP failures."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from amberclaw.agent.loop import AgentLoop
from amberclaw.bus.events import InboundMessage


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


async def test_stop_retains_and_drains_plugin_shutdown() -> None:
    agent = _make_runtime()
    agent._running = True
    agent._mcp_discovery_task = None
    agent._mcp_stack = None
    agent._plugin_stop_task = None
    agent.plugin_manager = AsyncMock()
    agent.stop()
    task = agent._plugin_stop_task
    assert isinstance(task, asyncio.Task)
    agent.stop()
    assert agent._plugin_stop_task is task
    await agent.close_mcp()
    agent.plugin_manager.stop.assert_awaited_once()
    assert agent._plugin_stop_task is None
    agent.stop()
    await agent.close_mcp()
    expected_stops = 2
    assert agent.plugin_manager.stop.await_count == expected_stops


async def test_mcp_failure_still_drains_plugin_shutdown() -> None:
    agent = _make_runtime()
    agent._running = True
    agent._mcp_discovery_task = None
    agent._plugin_stop_task = None
    agent.plugin_manager = AsyncMock()
    agent._mcp_stack = AsyncMock()
    agent._mcp_stack.aclose.side_effect = OSError("MCP failure")
    agent.stop()
    with pytest.raises(OSError, match="MCP failure"):
        await agent.close_mcp()
    agent.plugin_manager.stop.assert_awaited_once()
    assert agent._mcp_stack is None


async def test_restart_waits_for_shutdown_and_recreates_discovery() -> None:
    agent = _make_runtime()
    agent._running = True
    agent._mcp_stack = None
    agent._mcp_discovery_task = None
    agent._plugin_stop_task = None
    agent.plugin_manager = AsyncMock()
    agent.plugin_manager.proxy_tools = {}
    agent._connect_mcp = AsyncMock()
    agent._mcp_discovery_loop = AsyncMock()
    agent.tools = MagicMock()
    agent.bus = AsyncMock()
    agent.bus.consume_inbound.return_value = InboundMessage(
        channel="cli", sender_id="local", chat_id="direct", content="/stop"
    )

    async def finish_run(_message: InboundMessage) -> None:
        agent._running = False

    agent._handle_stop = AsyncMock(side_effect=finish_run)
    agent.stop()
    await agent.run()
    agent.plugin_manager.stop.assert_awaited_once()
    agent.plugin_manager.start.assert_awaited_once()
    assert agent._plugin_stop_task is None
    assert agent._mcp_discovery_task is not None
    agent.stop()
    await agent.close_mcp()
    assert agent._mcp_discovery_task is None
    assert agent._mcp_connected is False
