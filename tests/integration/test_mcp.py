# ruff: noqa: PLR2004, ARG001, PLC0415
"""Integration tests for Model Context Protocol (MCP) tool integration.

Validates:
1. MCPToolWrapper naming conventions and schema projection
2. Standard tool execution and text content aggregation
3. Task-based execution (2026 async MCP task spec)
4. Timeout and cancellation resilience
5. MCP discovery endpoint (.well-known/mcp.json)
6. MCP server connection and tool registry mounting
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from amberclaw.agent.tools.mcp import (
    MCPToolWrapper,
    connect_mcp_servers,
    discover_mcp_servers,
)
from amberclaw.agent.tools.registry import ToolRegistry


class MockMCPToolDef:
    def __init__(self, name: str, description: str, input_schema: dict):
        self.name = name
        self.description = description
        self.inputSchema = input_schema


@pytest.mark.asyncio
async def test_mcp_tool_wrapper_metadata():
    tool_def = MockMCPToolDef(
        name="query_db",
        description="Run read-only SQL query",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
    )
    session = AsyncMock()

    wrapper = MCPToolWrapper(
        session=session,
        server_name="postgres_service",
        tool_def=tool_def,
        tool_timeout=15,
    )

    assert wrapper.name == "mcp_postgres_service_query_db"
    assert wrapper.description == "Run read-only SQL query"
    assert wrapper.parameters == {
        "type": "object",
        "properties": {"query": {"type": "string"}},
    }


@pytest.mark.asyncio
async def test_mcp_tool_wrapper_standard_execution():
    tool_def = MockMCPToolDef(
        name="calculate",
        description="Performs arithmetic",
        input_schema={"type": "object"},
    )
    session = AsyncMock()
    session.supports_tasks = False
    mock_block_1 = SimpleNamespace(text="Result is: ")
    mock_block_2 = SimpleNamespace(text="42")
    session.call_tool.return_value = SimpleNamespace(
        content=[mock_block_1, mock_block_2]
    )

    wrapper = MCPToolWrapper(
        session=session,
        server_name="math_srv",
        tool_def=tool_def,
        tool_timeout=10,
    )

    output = await wrapper.execute(expr="6 * 7")
    assert output == "Result is: \n42"
    session.call_tool.assert_awaited_once_with("calculate", arguments={"expr": "6 * 7"})


@pytest.mark.asyncio
async def test_mcp_tool_wrapper_task_mode_execution():
    tool_def = MockMCPToolDef(
        name="deep_search",
        description="Long running search task",
        input_schema={},
    )
    session = AsyncMock()
    session.supports_tasks = True

    mock_task = AsyncMock()
    mock_task.id = "task-12345"
    mock_task.wait.return_value = SimpleNamespace(
        content=[SimpleNamespace(text="Task completed with 5 findings")]
    )
    session.create_task.return_value = mock_task

    wrapper = MCPToolWrapper(
        session=session,
        server_name="crawler",
        tool_def=tool_def,
        tool_timeout=10,
    )

    output = await wrapper.execute(query="security vulnerability")
    assert "Task completed with 5 findings" in output
    session.create_task.assert_awaited_once_with(
        "deep_search", arguments={"query": "security vulnerability"}
    )
    mock_task.wait.assert_awaited_once()


@pytest.mark.asyncio
async def test_mcp_tool_wrapper_timeout():
    tool_def = MockMCPToolDef(
        name="slow_task",
        description="Hangs indefinitely",
        input_schema={},
    )
    session = AsyncMock()
    session.supports_tasks = False

    async def hang(*args, **kwargs):
        await asyncio.sleep(1.0)

    session.call_tool.side_effect = hang

    wrapper = MCPToolWrapper(
        session=session,
        server_name="slow_srv",
        tool_def=tool_def,
        tool_timeout=0.05,
    )

    result = await wrapper.execute()
    assert "timed out after 0.05s" in result


@pytest.mark.asyncio
async def test_mcp_tool_wrapper_internal_cancellation():
    tool_def = MockMCPToolDef(
        name="cancelled_op",
        description="Fails with CancelledError internally",
        input_schema={},
    )
    session = AsyncMock()
    session.supports_tasks = False
    session.call_tool.side_effect = asyncio.CancelledError()

    wrapper = MCPToolWrapper(
        session=session,
        server_name="faulty_srv",
        tool_def=tool_def,
        tool_timeout=10,
    )

    result = await wrapper.execute()
    assert result == "(MCP tool call was cancelled)"


@pytest.mark.asyncio
async def test_mcp_tool_wrapper_generic_exception():
    tool_def = MockMCPToolDef(
        name="failing_tool",
        description="Fails with runtime exception",
        input_schema={},
    )
    session = AsyncMock()
    session.supports_tasks = False
    session.call_tool.side_effect = RuntimeError("Server disconnected unexpectedly")

    wrapper = MCPToolWrapper(
        session=session,
        server_name="err_srv",
        tool_def=tool_def,
        tool_timeout=10,
    )

    result = await wrapper.execute()
    assert "(MCP tool call failed: RuntimeError)" in result


@pytest.mark.asyncio
async def test_discover_mcp_servers():
    discovery_payload = {
        "servers": [
            {
                "name": "weather",
                "url": "http://localhost:8081/sse",
                "transport": "sse",
            },
            {
                "name": "finance",
                "url": "http://localhost:8082/sse",
                "transport": "sse",
            },
        ]
    }

    mock_resp = httpx.Response(200, json=discovery_payload)
    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        servers = await discover_mcp_servers("http://mock-hub.local")
        assert len(servers) == 2
        assert servers[0]["name"] == "weather"
        assert servers[1]["name"] == "finance"


@pytest.mark.asyncio
async def test_connect_mcp_servers_registration():
    registry = ToolRegistry()
    mock_session = AsyncMock()
    mock_tools_list = SimpleNamespace(
        tools=[
            MockMCPToolDef("fetch_metrics", "Fetch live system metrics", {}),
            MockMCPToolDef("ping", "Ping server", {}),
        ]
    )
    mock_session.list_tools.return_value = mock_tools_list

    class MockClientSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    class MockSSEClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return (AsyncMock(), AsyncMock())

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    mock_mcp = SimpleNamespace(
        ClientSession=MockClientSession,
        StdioServerParameters=SimpleNamespace,
    )
    mock_mcp_client = SimpleNamespace()
    mock_mcp_sse = SimpleNamespace(sse_client=MockSSEClient)
    mock_mcp_stdio = SimpleNamespace(stdio_client=AsyncMock())
    mock_mcp_streamable_http = SimpleNamespace(streamable_http_client=AsyncMock())

    server_cfg = SimpleNamespace(
        type="sse",
        url="http://localhost:9000/sse",
        transport="sse",
        command=None,
        headers={},
        env={},
        tool_timeout=10,
        discover=False,
    )
    servers = {"metrics_server": server_cfg}

    from contextlib import AsyncExitStack

    stack = AsyncExitStack()

    with patch.dict(
        "sys.modules",
        {
            "mcp": mock_mcp,
            "mcp.client": mock_mcp_client,
            "mcp.client.sse": mock_mcp_sse,
            "mcp.client.stdio": mock_mcp_stdio,
            "mcp.client.streamable_http": mock_mcp_streamable_http,
        },
    ):
        await connect_mcp_servers(servers, registry, stack)

        assert "mcp_metrics_server_fetch_metrics" in registry
        assert "mcp_metrics_server_ping" in registry
