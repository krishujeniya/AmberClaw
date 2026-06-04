"""Plugin manager orchestrating dynamic subprocess execution and RPC proxying."""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Any

from loguru import logger

from amberclaw.agent.tools.base import Tool
from amberclaw.plugins.registry import PluginRegistry


class PluginConnection:
    """Manages the stdout, stdin, and stderr communication streams of a plugin process."""

    def __init__(self, process: asyncio.subprocess.Process, plugin_name: str) -> None:
        self.process = process
        self.plugin_name = plugin_name
        self._next_id = 1
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._read_task: asyncio.Task | None = None
        self._stderr_task: asyncio.Task | None = None

    def start(self) -> None:
        """Starts background tasks for stdout routing and stderr logging."""
        self._read_task = asyncio.create_task(self._read_loop())
        self._stderr_task = asyncio.create_task(self._stderr_loop())

    async def _read_loop(self) -> None:
        """Continuously reads JSON-RPC responses from stdout."""
        try:
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    break
                try:
                    res = json.loads(line.decode("utf-8"))
                    req_id = res.get("id")
                    if req_id in self._pending:
                        self._pending[req_id].set_result(res)
                except Exception as e:
                    logger.error("RPC parse error in plugin '{}': {}", self.plugin_name, e)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("RPC read loop terminated for plugin '{}': {}", self.plugin_name, e)

    async def _stderr_loop(self) -> None:
        """Forwards plugin process stderr streams to the system log."""
        try:
            while True:
                line = await self.process.stderr.readline()
                if not line:
                    break
                logger.info("[Plugin {}]: {}", self.plugin_name, line.decode("utf-8").strip())
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Stderr reader loop terminated for plugin '{}': {}", self.plugin_name, e)

    async def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Sends a JSON-RPC 2.0 request and awaits the corresponding response."""
        req_id = self._next_id
        self._next_id += 1

        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[req_id] = future

        req = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": req_id,
        }

        try:
            self.process.stdin.write(json.dumps(req).encode("utf-8") + b"\n")
            await self.process.stdin.drain()
            # Wait for response with a timeout
            return await asyncio.wait_for(future, timeout=30.0)
        except TimeoutError:
            logger.error("Timeout waiting for plugin '{}' RPC response.", self.plugin_name)
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32001, "message": "Request timed out"},
                "id": req_id,
            }
        except Exception as e:
            logger.exception("Error executing RPC call on '{}': {}", self.plugin_name, e)
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32002, "message": f"Execution failed: {e}"},
                "id": req_id,
            }
        finally:
            self._pending.pop(req_id, None)

    async def close(self) -> None:
        """Gracefully terminates the plugin process and stops communication tasks."""
        if self._read_task:
            self._read_task.cancel()
        if self._stderr_task:
            self._stderr_task.cancel()

        try:
            self.process.stdin.close()
            await self.process.stdin.wait_closed()
        except Exception:
            pass

        try:
            self.process.terminate()
            await asyncio.wait_for(self.process.wait(), timeout=2.0)
        except Exception:
            try:
                self.process.kill()
                await self.process.wait()
            except Exception:
                pass


class PluginProxyTool(Tool):
    """Dynamic wrapper tool routing invocation parameters to the isolated plugin host."""

    def __init__(self, plugin_name: str, tool_metadata: dict[str, Any], manager: "PluginManager") -> None:
        super().__init__()
        self._plugin_name = plugin_name
        self._tool_metadata = tool_metadata
        self._manager = manager

    @property
    def name(self) -> str:
        return f"{self._plugin_name}_{self._tool_metadata['name']}"

    @property
    def description(self) -> str:
        return self._tool_metadata["description"]

    @property
    def parameters(self) -> dict[str, Any]:
        return self._tool_metadata["args_schema"]

    async def execute(self, **kwargs: Any) -> str:
        """Relay invocation to the corresponding plugin host runner."""
        return await self._manager.execute_tool(
            self._plugin_name, self._tool_metadata["name"], kwargs
        )


class PluginManager:
    """Manages the startup, discovery, registration, and communication of all plugins."""

    def __init__(self, workspace: Path, plugins_dir: Path | None = None) -> None:
        self.workspace = workspace
        self.plugins_dir = plugins_dir or (workspace / "plugins")
        self.registry = PluginRegistry(self.plugins_dir)
        self.connections: dict[str, PluginConnection] = {}
        self.proxy_tools: dict[str, list[PluginProxyTool]] = {}

    async def start(self) -> None:
        """Starts all discovered plugins and compiles their dynamic tool classes."""
        manifests = self.registry.discover_plugins()
        for name, manifest in manifests.items():
            try:
                plugin_dir, _ = self.registry.plugins[name]

                # Ensure PYTHONPATH is forwarded to find core codebase imports
                env = os.environ.copy()
                src_root = str(Path(__file__).resolve().parents[3])  # root src path
                env["PYTHONPATH"] = src_root + (
                    os.pathsep + env["PYTHONPATH"] if "PYTHONPATH" in env else ""
                )

                args = [
                    sys.executable,
                    "-m",
                    "amberclaw.plugins.host",
                    "--entrypoint",
                    str(plugin_dir / manifest.entrypoint),
                    "--capabilities",
                    ",".join(c.value for c in manifest.capabilities),
                    "--workspace",
                    str(self.workspace),
                    "--plugin-dir",
                    str(plugin_dir),
                ]

                process = await asyncio.create_subprocess_exec(
                    *args,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )

                conn = PluginConnection(process, name)
                conn.start()
                self.connections[name] = conn

                # Retrieve tool metadata
                res = await conn.call("get_tools", {})
                if "error" in res:
                    logger.error(
                        "Plugin '{}' failed to register tools: {}", name, res["error"]
                    )
                    await conn.close()
                    del self.connections[name]
                    continue

                tools_metadata = res.get("result", [])
                self.proxy_tools[name] = []
                for tool_meta in tools_metadata:
                    proxy = PluginProxyTool(name, tool_meta, self)
                    self.proxy_tools[name].append(proxy)

                logger.info("Successfully loaded plugin '{}' with {} tools.", name, len(tools_metadata))

            except Exception as e:
                logger.error("Failed to start plugin '{}': {}", name, e)

    async def execute_tool(self, plugin_name: str, tool_name: str, args: dict[str, Any]) -> str:
        """Forwards call execution request to the appropriate connection."""
        conn = self.connections.get(plugin_name)
        if not conn:
            return f"Error: Plugin '{plugin_name}' is not running."

        res = await conn.call("execute_tool", {"name": tool_name, "args": args})
        if "error" in res:
            err = res["error"]
            return f"Error executing plugin tool {tool_name}: {err.get('message')}"
        return res.get("result", "")

    async def stop(self) -> None:
        """Terminates all plugin host execution processes."""
        for name, conn in list(self.connections.items()):
            try:
                await conn.close()
            except Exception as e:
                logger.error("Error shutting down plugin '{}': {}", name, e)
        self.connections.clear()
        self.proxy_tools.clear()
