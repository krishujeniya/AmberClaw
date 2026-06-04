"""Unit tests for the AmberClaw plugin system."""

import os
import sys
import tempfile
import asyncio
from pathlib import Path
import pytest

from amberclaw.plugins import PluginManager, PluginCapability
from amberclaw.plugins.registry import PluginRegistry, PluginManifest
from amberclaw.security.landlock import IS_LINUX


@pytest.mark.asyncio
async def test_plugin_discovery_and_execution() -> None:
    # 1. Create a temporary plugin folder structure
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()

        # Write plugin.yaml manifest
        manifest_content = """
name: test_plugin
version: 1.0.0
description: "A test plugin for validation"
entrypoint: main.py
capabilities:
  - filesystem_read
"""
        (plugin_dir / "plugin.yaml").write_text(manifest_content, encoding="utf-8")

        # Write plugin entrypoint script
        main_py_content = """
from amberclaw.plugins.host import register_tool

@register_tool
def add(a: int, b: int) -> int:
    \"\"\"Add two numbers.\"\"\"
    return a + b

@register_tool
def attempt_write(path: str, content: str) -> str:
    \"\"\"Attempt to write to a path.\"\"\"
    with open(path, "w") as f:
        f.write(content)
    return "written"
"""
        (plugin_dir / "main.py").write_text(main_py_content, encoding="utf-8")

        # 2. Run registry discovery check
        registry = PluginRegistry(tmp_path)
        manifests = registry.discover_plugins()
        assert "test_plugin" in manifests
        manifest = manifests["test_plugin"]
        assert manifest.name == "test_plugin"
        assert manifest.entrypoint == "main.py"
        assert PluginCapability.FILESYSTEM_READ in manifest.capabilities
        assert PluginCapability.FILESYSTEM_WRITE not in manifest.capabilities

        # 3. Create another temp directory for workspace
        with tempfile.TemporaryDirectory() as workspace_dir:
            workspace_path = Path(workspace_dir)

            # Start PluginManager
            manager = PluginManager(workspace=workspace_path, plugins_dir=tmp_path)
            try:
                await manager.start()

                # Verify tools got discovered
                assert "test_plugin" in manager.proxy_tools
                tools = manager.proxy_tools["test_plugin"]
                assert len(tools) == 2

                # Verify dynamic schema structure
                add_tool = next(t for t in tools if t.name == "test_plugin_add")
                assert add_tool.description == "Add two numbers."
                params_schema = add_tool.parameters
                assert "properties" in params_schema
                assert "a" in params_schema["properties"]
                assert "b" in params_schema["properties"]

                # Verify execution
                res = await manager.execute_tool("test_plugin", "add", {"a": 10, "b": 20})
                assert res == "30"

                # Verify isolation if running on Linux with Landlock
                if IS_LINUX:
                    # Attempting to write to an outside path (e.g. system/tmp dir when not allowed) should fail
                    # Let's create a test target path outside the workspace (in home or another temp dir)
                    outside_path = Path(tmpdir) / "should_not_exist.txt"
                    
                    res_write = await manager.execute_tool(
                        "test_plugin", 
                        "attempt_write", 
                        {"path": str(outside_path), "content": "hello"}
                    )
                    # Check if error message reports PermissionError
                    assert "PermissionError" in res_write or "Permission denied" in res_write
                    assert not outside_path.exists()

            finally:
                await manager.stop()
