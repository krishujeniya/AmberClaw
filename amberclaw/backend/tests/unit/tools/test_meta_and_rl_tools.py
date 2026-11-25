# ruff: noqa: PLR2004
"""Unit tests for AmberClaw meta-tools and RL trajectory tools."""

import json

import pytest

from amberclaw.rl.trajectory import TrajectoryBuffer
from amberclaw.tools.meta_tools import InspectToolSchemaTool, ListToolsTool
from amberclaw.tools.registry import ToolRegistry
from amberclaw.tools.rl_tools import (
    RecordTrajectoryStepTool,
    RLBufferStatsTool,
    RLDiagnosticsTool,
)

# ==============================================================================
# Meta Tools Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_list_tools_tool():
    registry = ToolRegistry()
    list_tool = ListToolsTool(registry=registry)
    schema_tool = InspectToolSchemaTool(registry=registry)

    registry.register(list_tool)
    registry.register(schema_tool)

    # List all
    res_all = await list_tool.run()
    assert "list_tools" in res_all
    assert "inspect_tool_schema" in res_all

    # Filtered search
    res_filtered = await list_tool.run(filter_text="inspect")
    assert "inspect_tool_schema" in res_filtered
    assert "list_tools" not in res_filtered

    # No match
    res_empty = await list_tool.run(filter_text="nonexistent_xyz")
    assert "No tools matching filter" in res_empty


@pytest.mark.asyncio
async def test_inspect_tool_schema_tool():
    registry = ToolRegistry()
    list_tool = ListToolsTool(registry=registry)
    schema_tool = InspectToolSchemaTool(registry=registry)
    registry.register(list_tool)
    registry.register(schema_tool)

    raw_json = await schema_tool.run(tool_name="list_tools")
    data = json.loads(raw_json)
    assert data["name"] == "list_tools"
    assert "parameters" in data
    assert "properties" in data["parameters"]

    missing = await schema_tool.run(tool_name="phantom_tool")
    assert "not found" in missing


# ==============================================================================
# RL Tools Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_record_trajectory_step_and_stats():
    buffer = TrajectoryBuffer(max_size=50)
    record_tool = RecordTrajectoryStepTool(buffer=buffer)
    stats_tool = RLBufferStatsTool(buffer=buffer)

    # Record first step
    out1 = await record_tool.run(
        episode_id="ep-101",
        action="search_web(query='python 3.12')",
        reward=0.5,
        done=False,
    )
    assert "Step recorded for episode 'ep-101'" in out1
    assert "step count: 1" in out1

    # Record terminal step
    out2 = await record_tool.run(
        episode_id="ep-101",
        action="synthesize_answer()",
        reward=1.0,
        done=True,
    )
    assert "step count: 2" in out2
    assert "current total reward: 1.50" in out2

    # Check stats
    stats_raw = await stats_tool.run()
    stats = json.loads(stats_raw)
    assert stats["total_episodes"] == 1
    assert stats["total_steps"] == 2
    assert stats["mean_episode_reward"] == 1.5


@pytest.mark.asyncio
async def test_rl_diagnostics_tool():
    diag_tool = RLDiagnosticsTool()
    raw_diag = await diag_tool.run()
    diag = json.loads(raw_diag)
    assert "has_cuda" in diag
    assert "recommended_device" in diag
