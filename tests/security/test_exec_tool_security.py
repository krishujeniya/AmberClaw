import pytest
from pathlib import Path
from amberclaw.agent.tools.shell import ExecTool, ExecArgs


@pytest.fixture
def exec_tool(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return ExecTool(working_dir=str(workspace), restrict_to_workspace=True)


@pytest.mark.asyncio
async def test_exec_tool_blocks_dangerous_rm(exec_tool):
    result = await exec_tool.run(ExecArgs(command="rm -rf /"))
    assert "Error: Command blocked by safety guard" in result


@pytest.mark.asyncio
async def test_exec_tool_blocks_dd(exec_tool):
    result = await exec_tool.run(ExecArgs(command="dd if=/dev/zero of=/dev/sda"))
    assert "Error: Command blocked by safety guard" in result


@pytest.mark.asyncio
async def test_exec_tool_blocks_shutdown(exec_tool):
    result = await exec_tool.run(ExecArgs(command="shutdown -h now"))
    assert "Error: Command blocked by safety guard" in result


@pytest.mark.asyncio
async def test_exec_tool_blocks_reboot(exec_tool):
    result = await exec_tool.run(ExecArgs(command="reboot"))
    assert "Error: Command blocked by safety guard" in result


@pytest.mark.asyncio
async def test_exec_tool_blocks_fork_bomb(exec_tool):
    result = await exec_tool.run(ExecArgs(command=":() { :|:& }; :"))
    assert "Error: Command blocked by safety guard" in result


@pytest.mark.asyncio
async def test_exec_tool_blocks_path_traversal(exec_tool):
    result = await exec_tool.run(ExecArgs(command="cat ../../etc/passwd"))
    assert "Error: Command blocked by safety guard" in result


@pytest.mark.asyncio
async def test_exec_tool_blocks_outside_absolute_path(exec_tool):
    result = await exec_tool.run(ExecArgs(command="cat /etc/passwd"))
    assert "Error: Command blocked by safety guard" in result


@pytest.mark.asyncio
async def test_exec_tool_allows_safe_command(exec_tool):
    result = await exec_tool.run(ExecArgs(command="echo 'Hello AmberClaw Security'"))
    assert "Hello AmberClaw Security" in result
