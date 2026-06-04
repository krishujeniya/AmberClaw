"""Out-of-process host for running AmberClaw plugins in isolated environments."""

import argparse
import asyncio
import importlib.util
import inspect
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

from pydantic import create_model

from amberclaw.plugins.capabilities import PluginCapability, apply_sandbox_with_capabilities

# In-memory registry of tools exposed by the plugin
REGISTERED_TOOLS: dict[str, dict[str, Any]] = {}


def register_tool(func: Callable) -> Callable:
    """Decorator to register a function as a plugin tool."""
    name = func.__name__
    doc = func.__doc__ or f"Execute {name}"

    # Analyze signature and create Pydantic model for validation
    sig = inspect.signature(func)
    fields = {}
    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue
        annotation = (
            param.annotation
            if param.annotation is not inspect.Parameter.empty
            else Any
        )
        default = (
            param.default
            if param.default is not inspect.Parameter.empty
            else ...
        )
        fields[param_name] = (annotation, default)

    model_name = f"{name}_args"
    args_schema = create_model(model_name, **fields)

    REGISTERED_TOOLS[name] = {
        "func": func,
        "description": doc.strip(),
        "args_schema": args_schema,
    }
    return func


def scan_and_register_module_functions(module: Any) -> None:
    """Auto-register public functions defined in the entrypoint module."""
    for name, obj in inspect.getmembers(module):
        if (
            inspect.isfunction(obj)
            and not name.startswith("_")
            and obj.__module__ == module.__name__
        ):
            if name not in REGISTERED_TOOLS:
                register_tool(obj)


def load_plugin(entrypoint_path: Path) -> Any:
    """Dynamically loads the python entrypoint file as a module."""
    if not entrypoint_path.exists():
        raise FileNotFoundError(f"Entrypoint file not found: {entrypoint_path}")

    # Add the plugin directory to path for relative imports
    plugin_dir = entrypoint_path.parent
    if str(plugin_dir) not in sys.path:
        sys.path.insert(0, str(plugin_dir))

    spec = importlib.util.spec_from_file_location("plugin_entrypoint", str(entrypoint_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec for {entrypoint_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def handle_request(req: dict[str, Any]) -> dict[str, Any]:
    """Processes a JSON-RPC 2.0 request and returns the response."""
    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})

    if method == "get_tools":
        tools_list = []
        for name, info in REGISTERED_TOOLS.items():
            schema = info["args_schema"].model_json_schema()
            # Clean up schema for LLM routing consistency
            schema.pop("title", None)
            if "properties" in schema:
                for prop in schema["properties"].values():
                    prop.pop("title", None)

            tools_list.append(
                {
                    "name": name,
                    "description": info["description"],
                    "args_schema": schema,
                }
            )
        return {"jsonrpc": "2.0", "result": tools_list, "id": req_id}

    elif method == "execute_tool":
        tool_name = params.get("name")
        tool_args = params.get("args", {})

        if tool_name not in REGISTERED_TOOLS:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32601,
                    "message": f"Tool '{tool_name}' not found.",
                },
                "id": req_id,
            }

        info = REGISTERED_TOOLS[tool_name]
        func = info["func"]
        args_schema = info["args_schema"]

        try:
            # Validate input arguments via Pydantic model
            validated = args_schema.model_validate(tool_args)
            func_args = validated.model_dump()

            # Execute tool safely
            if inspect.iscoroutinefunction(func):
                result = await func(**func_args)
            else:
                result = await asyncio.to_thread(func, **func_args)

            return {"jsonrpc": "2.0", "result": str(result), "id": req_id}

        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32000,
                    "message": str(e),
                    "data": traceback.format_exc(),
                },
                "id": req_id,
            }
    else:
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32601,
                "message": f"Method '{method}' not found.",
            },
            "id": req_id,
        }


async def main() -> None:
    parser = argparse.ArgumentParser(description="AmberClaw Plugin Host")
    parser.add_argument("--entrypoint", required=True, help="Path to plugin entrypoint .py file")
    parser.add_argument("--capabilities", default="", help="Comma-separated capability list")
    parser.add_argument("--workspace", required=True, help="Workspace path")
    parser.add_argument("--plugin-dir", required=True, help="Plugin directory path")

    args = parser.parse_args()

    # Parse capabilities
    caps = []
    if args.capabilities:
        for val in args.capabilities.split(","):
            val_clean = val.strip()
            if val_clean:
                try:
                    caps.append(PluginCapability(val_clean))
                except ValueError:
                    sys.stderr.write(f"Warning: Unknown capability '{val_clean}' ignored.\n")

    # Load the plugin module first to register tools
    try:
        module = load_plugin(Path(args.entrypoint))
        scan_and_register_module_functions(module)
    except Exception as e:
        sys.stderr.write(f"Failed to load plugin: {e}\n")
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

    # Restrict current host process before starting I/O loop
    apply_sandbox_with_capabilities(caps, Path(args.workspace), Path(args.plugin_dir))

    # Read/write loop on stdin/stdout
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        line = await reader.readline()
        if not line:
            break

        try:
            req = json.loads(line.decode("utf-8"))
            res = await handle_request(req)
        except Exception as e:
            res = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32700,
                    "message": f"Parse error or execution failure: {e}",
                },
                "id": None,
            }

        try:
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()
        except Exception as e:
            sys.stderr.write(f"Failed to write RPC response: {e}\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
