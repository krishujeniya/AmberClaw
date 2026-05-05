"""MCP client: connects to MCP servers and wraps their tools as native amberclaw tools."""

import asyncio
from contextlib import AsyncExitStack
from typing import Any

import httpx
from loguru import logger

from amberclaw.agent.tools.base import Tool
from amberclaw.agent.tools.registry import ToolRegistry


async def discover_mcp_servers(host_url: str) -> list[dict]:
    """
    Discover MCP servers via .well-known/mcp.json.
    Returns a list of server configurations.
    """
    discovery_url = f"{host_url.rstrip('/')}/.well-known/mcp.json"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(discovery_url)
            if resp.status_code == 200:
                data = resp.json()
                servers = data.get("servers", [])
                logger.info("Found {} MCP servers via discovery at {}", len(servers), host_url)
                return servers
    except Exception as e:
        logger.debug("MCP discovery failed at {}: {}", discovery_url, e)
    return []


class MCPToolWrapper(Tool):
    """Wraps a single MCP server tool as a amberclaw Tool."""

    def __init__(self, session, server_name: str, tool_def, tool_timeout: int = 30):
        self._session = session
        self._original_name = tool_def.name
        self._name = f"mcp_{server_name}_{tool_def.name}"
        self._description = tool_def.description or tool_def.name
        self._parameters = tool_def.inputSchema or {"type": "object", "properties": {}}
        self._tool_timeout = tool_timeout

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._parameters

    async def execute(self, **kwargs: Any) -> str:
        from mcp import types

        try:
            # Check if this tool should be called as a task (2026 spec)
            is_task = getattr(self._session, "supports_tasks", False) and hasattr(
                self._session, "create_task"
            )

            if is_task:
                # Long-running task support
                task = await self._session.create_task(self._original_name, arguments=kwargs)
                logger.info("MCP task '{}' started: {}", self._name, task.id)
                result = await asyncio.wait_for(task.wait(), timeout=self._tool_timeout)
            else:
                # Standard tool call
                result = await asyncio.wait_for(
                    self._session.call_tool(self._original_name, arguments=kwargs),
                    timeout=self._tool_timeout,
                )
        except asyncio.TimeoutError:
            logger.warning("MCP tool '{}' timed out after {}s", self._name, self._tool_timeout)
            return f"(MCP tool call timed out after {self._tool_timeout}s)"
        except asyncio.CancelledError:
            # MCP SDK's anyio cancel scopes can leak CancelledError on timeout/failure.
            # Re-raise only if our task was externally cancelled (e.g. /stop).
            task = asyncio.current_task()
            if task is not None and task.cancelling() > 0:
                raise
            logger.warning("MCP tool '{}' was cancelled by server/SDK", self._name)
            return "(MCP tool call was cancelled)"
        except Exception as exc:
            logger.exception(
                "MCP tool '{}' failed: {}: {}",
                self._name,
                type(exc).__name__,
                exc,
            )
            return f"(MCP tool call failed: {type(exc).__name__})"

        # Handle text content
        content = getattr(result, "content", [])
        if not isinstance(content, list):
            content = [content] if content else []

        parts = []
        try:
            from mcp import types

            for block in content:
                if isinstance(block, types.TextContent):
                    parts.append(block.text)
                elif hasattr(block, "text"):
                    parts.append(getattr(block, "text"))
                else:
                    parts.append(str(block))
        except ImportError:
            # Fallback if mcp.types is not available
            for block in content:
                if hasattr(block, "text"):
                    parts.append(getattr(block, "text"))
                elif isinstance(block, dict) and "text" in block:
                    parts.append(block["text"])
                else:
                    parts.append(str(block))

        return "\n".join(parts) or "(no output)"


async def connect_mcp_servers(
    mcp_servers: dict, registry: ToolRegistry, stack: AsyncExitStack
) -> None:
    """Connect to configured MCP servers and register their tools."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.sse import sse_client
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamable_http_client

    # Expand discovery servers
    discovery_queue = []
    for name, cfg in mcp_servers.items():
        if getattr(cfg, "discover", False) and cfg.url:
            discovered = await discover_mcp_servers(cfg.url)
            for d_cfg in discovered:
                discovery_queue.append((d_cfg.get("name", name), d_cfg))

    # Add discovered to main loop
    for d_name, d_cfg_dict in discovery_queue:
        from types import SimpleNamespace

        # Convert dict to namespace to match expected cfg object
        mcp_servers[d_name] = SimpleNamespace(**d_cfg_dict)

    for name, cfg in mcp_servers.items():
        try:
            transport_type = cfg.type
            if not transport_type:
                if cfg.command:
                    transport_type = "stdio"
                elif cfg.url:
                    # Convention: URLs ending with /sse use SSE transport; others use streamableHttp
                    transport_type = (
                        "sse" if cfg.url.rstrip("/").endswith("/sse") else "streamableHttp"
                    )
                else:
                    logger.warning("MCP server '{}': no command or url configured, skipping", name)
                    continue

            if transport_type == "stdio":
                params = StdioServerParameters(
                    command=cfg.command, args=cfg.args, env=cfg.env or None
                )
                read, write = await stack.enter_async_context(stdio_client(params))
            elif transport_type == "sse":

                def httpx_client_factory(
                    headers: dict[str, str] | None = None,
                    timeout: httpx.Timeout | None = None,
                    auth: httpx.Auth | None = None,
                ) -> httpx.AsyncClient:
                    merged_headers = {**(cfg.headers or {}), **(headers or {})}
                    return httpx.AsyncClient(
                        headers=merged_headers or None,
                        follow_redirects=True,
                        timeout=timeout,
                        auth=auth,
                    )

                read, write = await stack.enter_async_context(
                    sse_client(cfg.url, httpx_client_factory=httpx_client_factory)
                )
            elif transport_type == "streamableHttp":
                # Always provide an explicit httpx client so MCP HTTP transport does not
                # inherit httpx's default 5s timeout and preempt the higher-level tool timeout.
                http_client = await stack.enter_async_context(
                    httpx.AsyncClient(
                        headers=cfg.headers or None,
                        follow_redirects=True,
                        timeout=None,
                    )
                )
                read, write, _ = await stack.enter_async_context(
                    streamable_http_client(cfg.url, http_client=http_client)
                )
            else:
                logger.warning("MCP server '{}': unknown transport type '{}'", name, transport_type)
                continue

            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            tools = await session.list_tools()
            for tool_def in tools.tools:
                wrapper = MCPToolWrapper(session, name, tool_def, tool_timeout=cfg.tool_timeout)
                registry.register(wrapper)
                logger.debug("MCP: registered tool '{}' from server '{}'", wrapper.name, name)

            logger.info("MCP server '{}': connected, {} tools registered", name, len(tools.tools))
        except Exception as e:
            logger.error("MCP server '{}': failed to connect: {}", name, e)
