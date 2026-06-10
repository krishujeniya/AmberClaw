import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from amberclaw.terminal.factory import BackendFactory
from amberclaw.terminal.modal import ModalTerminalBackend


@pytest.mark.asyncio
async def test_modal_connect_success() -> None:
    """Test connect uses lookup if already deployed."""
    mock_func = MagicMock()
    with patch("modal.Function.from_name", return_value=mock_func) as mock_lookup:
        backend = ModalTerminalBackend(workspace_dir="/dummy/workspace", app_name="test-app")
        await backend.connect()
        
        assert backend._connected is True
        mock_lookup.assert_called_once_with("test-app", "run_bash")


@pytest.mark.asyncio
async def test_modal_connect_fallback_deploy() -> None:
    """Test connect deploys if lookup fails."""
    with patch("modal.Function.from_name", side_effect=Exception("Not found")), \
         patch("amberclaw.terminal.modal.app.deploy") as mock_deploy:
         
        backend = ModalTerminalBackend(workspace_dir="/dummy/workspace", app_name="test-app")
        await backend.connect()
        
        assert backend._connected is True
        mock_deploy.assert_called_once_with(name="test-app")


@pytest.mark.asyncio
async def test_modal_sync_workspace() -> None:
    """Test workspace synchronization upload logic."""
    mock_volume = MagicMock()
    
    with patch("modal.NetworkFileSystem.from_name", return_value=mock_volume) as mock_from_name, \
         patch("modal.Function.from_name", return_value=MagicMock()), \
         patch("os.walk") as mock_walk, \
         patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.open") as mock_open:
         
        # Mock directory structure: 1 file
        mock_walk.return_value = [("/dummy/workspace", [], ["test.txt"])]
        
        # Mock file hash check
        mock_file = MagicMock()
        mock_file.read.side_effect = [b"file content", b""]
        mock_open.return_value.__enter__.return_value = mock_file
        
        backend = ModalTerminalBackend(workspace_dir="/dummy/workspace")
        await backend._sync_workspace()
        
        mock_from_name.assert_called_once_with("amberclaw-workspace")
        mock_volume.write_file.assert_called_once()


@pytest.mark.asyncio
async def test_modal_execute_bash() -> None:
    """Test remote bash execution and result structure."""
    mock_func = MagicMock()
    mock_func.remote.return_value = {
        "stdout": "bash output",
        "stderr": "",
        "exit_code": 0,
        "execution_time_ms": 42.0,
    }
    
    with patch("modal.Function.from_name", return_value=mock_func), \
         patch("amberclaw.terminal.modal.ModalTerminalBackend._sync_workspace", new_callable=AsyncMock):
         
        backend = ModalTerminalBackend(workspace_dir="/dummy/workspace")
        result = await backend.execute_bash("echo 'hello'", timeout=10)
        
        assert result["stdout"] == "bash output"
        assert result["stderr"] == ""
        assert result["exit_code"] == 0
        assert result["execution_time_ms"] == 42.0  # noqa: PLR2004
        mock_func.remote.assert_called_once_with("echo 'hello'")


@pytest.mark.asyncio
async def test_modal_execute_python() -> None:
    """Test remote python execution with environment propagation."""
    mock_func = MagicMock()
    mock_func.remote.return_value = {
        "stdout": "py output",
        "stderr": "",
        "exit_code": 0,
        "execution_time_ms": 10.0,
    }
    
    with patch("modal.Function.from_name", return_value=mock_func), \
         patch("amberclaw.terminal.modal.ModalTerminalBackend._sync_workspace", new_callable=AsyncMock):
         
        backend = ModalTerminalBackend(workspace_dir="/dummy/workspace")
        custom_env = {"VAR1": "VAL1"}
        result = await backend.execute_python("print('hi')", timeout=10, env=custom_env)
        
        assert result["stdout"] == "py output"
        assert result["exit_code"] == 0
        mock_func.remote.assert_called_once_with("print('hi')", custom_env)


@pytest.mark.asyncio
async def test_modal_timeout_handling() -> None:
    """Test timeout handling mapped to exit_code -9."""
    mock_func = MagicMock()
    # Mock remote to block
    def block_call(*_args: Any, **_kwargs: Any) -> None:
        time.sleep(5)
        
    mock_func.remote.side_effect = block_call
    
    with patch("modal.Function.from_name", return_value=mock_func), \
         patch("amberclaw.terminal.modal.ModalTerminalBackend._sync_workspace", new_callable=AsyncMock):
         
        backend = ModalTerminalBackend(workspace_dir="/dummy/workspace")
        # Run with short timeout
        result = await backend.execute_bash("sleep 10", timeout=1)
        
        assert result["exit_code"] == -9  # noqa: PLR2004
        assert "Timeout Error" in result["stderr"]


@pytest.mark.asyncio
async def test_factory_modal_instantiation() -> None:
    """Test BackendFactory returns a correct ModalTerminalBackend."""
    backend = BackendFactory.create_backend(
        backend_type="modal",
        workspace_dir="/dummy/workspace",
        app_name="my-custom-sandbox",
    )
    
    assert isinstance(backend, ModalTerminalBackend)
    assert backend.workspace_dir == "/dummy/workspace"
    assert backend.app_name == "my-custom-sandbox"
