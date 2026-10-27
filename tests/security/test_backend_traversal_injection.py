"""Security tests verifying that execution backends and tool sandboxes reject path traversal and dangerous injection."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from amberclaw.agent.tools.shell import ExecArgs, ExecTool
from amberclaw.security.filters import ArgumentValidationError, ToolExecutionFilter
from amberclaw.terminal.docker import DockerTerminalBackend
from amberclaw.terminal.factory import BackendFactory
from amberclaw.terminal.local import LocalTerminalBackend


@pytest.fixture
def test_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "sandbox_ws"
    ws.mkdir()
    return ws


@pytest.mark.asyncio
async def test_exec_tool_rejects_path_traversal_and_escapes(test_workspace: Path):
    tool = ExecTool(working_dir=str(test_workspace), restrict_to_workspace=True)

    dangerous_commands = [
        "cat ../../../etc/shadow",
        "cat ../../etc/passwd",
        "tail -f /etc/shadow",
        "cat /etc/passwd",
    ]

    for cmd in dangerous_commands:
        result = await tool.run(ExecArgs(command=cmd))
        assert "Error: Command blocked by safety guard" in result


@pytest.mark.asyncio
async def test_exec_tool_rejects_command_injection_and_destructive_payloads(
    test_workspace: Path,
):
    tool = ExecTool(working_dir=str(test_workspace), restrict_to_workspace=True)

    destructive = [
        "rm -rf /",
        "mkfs.ext4 /dev/sda1",
        "dd if=/dev/zero of=/dev/sda",
        ":(){ :|:& };:",
        "reboot",
        "shutdown -r now",
    ]

    for cmd in destructive:
        result = await tool.run(ExecArgs(command=cmd))
        assert "Error: Command blocked by safety guard" in result


def test_tool_execution_filter_rejects_traversal_in_backend_params():
    traversal_payloads = [
        {"path": "../../sensitive/data.env"},
        {"file": "..\\windows\\system32"},
        {"filename": "normal%2e%2e/escape"},
        {"input": "data\x00/etc/passwd"},
    ]

    for payload in traversal_payloads:
        with pytest.raises(ArgumentValidationError) as exc_info:
            ToolExecutionFilter.validate_arguments(
                "terminal_backend",
                payload,
                block_traversal=True,
            )
        assert "Path traversal pattern detected" in str(exc_info.value)


@pytest.mark.asyncio
async def test_docker_backend_enforces_read_only_rootfs_and_network_none(
    test_workspace: Path,
):
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"container-id", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        backend = DockerTerminalBackend(workspace_dir=str(test_workspace))
        await backend.start()

        # Check docker run parameters
        run_args = mock_exec.call_args_list[2][0]
        assert "--read-only" in run_args
        assert "--network" in run_args
        assert "none" in run_args
        assert "--security-opt=no-new-privileges" in run_args
        await backend.stop()


def test_backend_factory_creates_supported_backends(test_workspace: Path):
    local_backend = BackendFactory.create_backend(
        "local", workspace_dir=str(test_workspace)
    )
    assert isinstance(local_backend, LocalTerminalBackend)

    docker_backend = BackendFactory.create_backend(
        "docker", workspace_dir=str(test_workspace)
    )
    assert isinstance(docker_backend, DockerTerminalBackend)
