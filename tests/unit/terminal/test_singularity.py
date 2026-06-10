import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from amberclaw.terminal.factory import BackendFactory
from amberclaw.terminal.singularity import SingularityTerminalBackend


@pytest.mark.asyncio
async def test_singularity_binary_resolution() -> None:
    """Test resolution of singularity vs apptainer binaries."""
    # Scenario 1: Apptainer is present
    with patch("shutil.which", side_effect=lambda bin_name: "/usr/bin/apptainer" if bin_name == "apptainer" else None):
        backend = SingularityTerminalBackend(workspace_dir="/dummy/workspace")
        assert backend._binary == "apptainer"

    # Scenario 2: Singularity only is present
    with patch("shutil.which", side_effect=lambda bin_name: "/usr/bin/singularity" if bin_name == "singularity" else None):
        backend = SingularityTerminalBackend(workspace_dir="/dummy/workspace")
        assert backend._binary == "singularity"

    # Scenario 3: Neither is present (defaults to singularity with warning)
    with patch("shutil.which", return_value=None):
        backend = SingularityTerminalBackend(workspace_dir="/dummy/workspace")
        assert backend._binary == "singularity"


@pytest.mark.asyncio
async def test_singularity_execute_bash() -> None:
    """Test bash command execution inside the Singularity/Apptainer container."""
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"hello from singularity", b"")

    # Apptainer is resolved
    with patch("shutil.which", side_effect=lambda bin_name: "/usr/bin/apptainer" if bin_name == "apptainer" else None), \
         patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
         
        backend = SingularityTerminalBackend(
            workspace_dir="/dummy/workspace",
            image="docker://python:3.11-slim"
        )
        
        result = await backend.execute_bash("echo 'hello'", timeout=12)
        
        # Verify call arguments
        mock_exec.assert_called_once_with(
            "apptainer",
            "exec",
            "--containall",
            "--no-home",
            "--cleanenv",
            "-B",
            "/dummy/workspace:/workspace",
            "--pwd",
            "/workspace",
            "docker://python:3.11-slim",
            "bash",
            "-s",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        assert result["stdout"] == "hello from singularity"
        assert result["stderr"] == ""
        assert result["exit_code"] == 0


@pytest.mark.asyncio
async def test_singularity_execute_python_with_env() -> None:
    """Test python script execution with environment variables propagation."""
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"py output", b"")

    # Singularity only is resolved
    with patch("shutil.which", side_effect=lambda bin_name: "/usr/bin/singularity" if bin_name == "singularity" else None), \
         patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
         
        backend = SingularityTerminalBackend(
            workspace_dir="/dummy/workspace",
            image="/path/to/image.sif"
        )
        
        custom_env = {"MY_VAR": "val1", "OTHER": "val2"}
        result = await backend.execute_python(
            "print('test')",
            timeout=25,
            env=custom_env,
        )
        
        # Verify call arguments and environment propagation
        mock_exec.assert_called_once_with(
            "singularity",
            "exec",
            "--containall",
            "--no-home",
            "--cleanenv",
            "-B",
            "/dummy/workspace:/workspace",
            "--pwd",
            "/workspace",
            "/path/to/image.sif",
            "python",
            "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={
                "SINGULARITYENV_MY_VAR": "val1",
                "APPTAINERENV_MY_VAR": "val1",
                "SINGULARITYENV_OTHER": "val2",
                "APPTAINERENV_OTHER": "val2",
            }
        )
        
        assert result["stdout"] == "py output"
        assert result["exit_code"] == 0


@pytest.mark.asyncio
async def test_singularity_timeout_handling() -> None:
    """Test timeout handling mapping to negative exit code -9."""
    mock_proc = AsyncMock()
    mock_proc.terminate = MagicMock()
    mock_proc.communicate.side_effect = TimeoutError("Timed out")
    
    with patch("shutil.which", side_effect=lambda bin_name: "/usr/bin/singularity" if bin_name == "singularity" else None), \
         patch("asyncio.create_subprocess_exec", return_value=mock_proc):
         
        backend = SingularityTerminalBackend(workspace_dir="/dummy/workspace")
        result = await backend.execute_bash("sleep 100", timeout=1)
        
        assert result["exit_code"] == -9  # noqa: PLR2004
        assert "Timeout Error" in result["stderr"]
        
        # Verify that terminate is called and waited
        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_awaited_once()


@pytest.mark.asyncio
async def test_singularity_exception_handling() -> None:
    """Test generic execution errors fallback gracefully."""
    with patch("shutil.which", side_effect=lambda bin_name: "/usr/bin/singularity" if bin_name == "singularity" else None), \
         patch("asyncio.create_subprocess_exec", side_effect=Exception("Binary missing")):
         
        backend = SingularityTerminalBackend(workspace_dir="/dummy/workspace")
        result = await backend.execute_bash("echo 'hello'")
        
        assert result["exit_code"] == -1
        assert "Binary missing" in result["stderr"]


@pytest.mark.asyncio
async def test_factory_singularity_instantiation() -> None:
    """Test BackendFactory returns a correct SingularityTerminalBackend."""
    with patch("shutil.which", side_effect=lambda bin_name: "/usr/bin/singularity" if bin_name == "singularity" else None):
        backend = BackendFactory.create_backend(
            backend_type="singularity",
            workspace_dir="/dummy/workspace",
            image="docker://ubuntu:latest"
        )
        
        assert isinstance(backend, SingularityTerminalBackend)
        assert backend.workspace_dir == "/dummy/workspace"
        assert backend.image == "docker://ubuntu:latest"
        assert backend._binary == "singularity"
