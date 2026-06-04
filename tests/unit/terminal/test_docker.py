from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from amberclaw.security.sandbox import CodeSandbox
from amberclaw.terminal.docker import DockerTerminalBackend


@pytest.mark.asyncio
async def test_docker_backend_lifecycle_and_execution() -> None:
    # We mock create_subprocess_exec to simulate docker CLI presence and successful run
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"container-id-abc", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        backend = DockerTerminalBackend(workspace_dir="/dummy/workspace")
        
        # Test start
        await backend.start()
        assert backend.container_running is True
        
        # Verify container was started with right args
        # The third mock call should be the docker run
        docker_run_args = mock_exec.call_args_list[2][0]
        assert "docker" in docker_run_args
        assert "run" in docker_run_args
        assert "--network" in docker_run_args
        assert "none" in docker_run_args
        assert "--read-only" in docker_run_args
        assert "--security-opt=no-new-privileges" in docker_run_args
        assert "/dummy/workspace:/workspace" in docker_run_args[docker_run_args.index("-v") + 1]

        # Test execute_bash
        mock_proc.communicate.return_value = (b"output from bash", b"")
        res = await backend.execute_bash("echo 'hello'")
        assert res["stdout"] == "output from bash"
        assert res["exit_code"] == 0

        # Test execute_python
        mock_proc.communicate.return_value = (b"output from python", b"")
        res_py = await backend.execute_python("print('hello')")
        assert res_py["stdout"] == "output from python"
        assert res_py["exit_code"] == 0

        # Test stop
        await backend.stop()
        assert backend.container_running is False


@pytest.mark.asyncio
async def test_docker_backend_validation_failure() -> None:
    # We mock create_subprocess_exec to fail the sandbox validation check
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        backend = DockerTerminalBackend(workspace_dir="/dummy/workspace")

        # Mock execute_python to return an exit code indicating failure (e.g. 1 for write failure)
        original_execute_python = backend.execute_python
        
        async def mock_execute_python(*args, **kwargs):
            res = await original_execute_python(*args, **kwargs)
            res["exit_code"] = 1
            return res
            
        backend.execute_python = mock_execute_python

        with pytest.raises(RuntimeError, match="Sandbox Validation Failed"):
            await backend.start()

        # The container should have been stopped and removed, so running state is false
        assert backend.container_running is False

@pytest.mark.asyncio
async def test_codesandbox_fallback_when_docker_fails() -> None:
    # Test that CodeSandbox correctly falls back to local execution when Docker fails
    sandbox = CodeSandbox(use_docker=True, workspace="/dummy/workspace")
    
    # We trigger local execution path in CodeSandbox by raising exception in Docker backend
    sandbox._docker_backend = MagicMock()
    sandbox._docker_backend.execute_python = AsyncMock(side_effect=Exception("Docker failed"))
    
    # Since execute_python catches the exception and falls back to local code,
    # it should run the local code block. We mock create_subprocess_exec to simulate local python run.
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"fallback success", b"")
    
    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await sandbox.execute_python("print('test')")
        assert result.stdout == "fallback success"
        assert result.exit_code == 0
