import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from e2b import CommandExitException, TimeoutException

from amberclaw.terminal.e2b import E2BTerminalBackend
from amberclaw.terminal.factory import BackendFactory


@pytest.mark.asyncio
async def test_e2b_backend_factory_creation() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = BackendFactory.create_backend(
            "e2b",
            workspace_dir=tmpdir,
            api_key="test-key",
            template="test-template",
        )
        assert isinstance(backend, E2BTerminalBackend)
        assert backend.workspace_dir == str(Path(tmpdir).resolve())  # noqa: ASYNC240
        assert backend.api_key == "test-key"
        assert backend.template == "test-template"


@pytest.mark.asyncio
@patch("amberclaw.terminal.e2b.AsyncSandbox")
async def test_e2b_backend_successful_bash_execution(
    mock_async_sandbox: MagicMock,
) -> None:
    # Set up mocks
    mock_sandbox_instance = MagicMock()
    mock_async_sandbox.create = AsyncMock(return_value=mock_sandbox_instance)

    mock_sandbox_instance.files.write_files = AsyncMock()
    mock_sandbox_instance.sandbox_id = "test-sandbox-id"

    # Mock command run result
    mock_result = MagicMock()
    mock_result.stdout = "hello from e2b"
    mock_result.stderr = ""
    mock_result.exit_code = 0
    mock_sandbox_instance.commands.run = AsyncMock(return_value=mock_result)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a file to test workspace sync
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("file content")

        backend = E2BTerminalBackend(workspace_dir=tmpdir, api_key="dummy-key")
        res = await backend.execute_bash("echo 'hello from e2b'")

        # Verify AsyncSandbox creation was called with credentials
        mock_async_sandbox.create.assert_called_once_with(api_key="dummy-key")

        # Verify sync uploaded files to /home/user/test.txt
        mock_sandbox_instance.files.write_files.assert_called_once()
        uploaded_files = mock_sandbox_instance.files.write_files.call_args[0][0]
        assert len(uploaded_files) == 1
        assert uploaded_files[0]["path"] == "/home/user/test.txt"
        assert uploaded_files[0]["data"] == b"file content"

        # Verify command execution result
        assert res["exit_code"] == 0
        assert res["stdout"] == "hello from e2b"
        assert res["stderr"] == ""
        assert res["execution_time_ms"] > 0
        mock_sandbox_instance.commands.run.assert_called_once_with(
            "echo 'hello from e2b'", timeout=30
        )


@pytest.mark.asyncio
@patch("amberclaw.terminal.e2b.AsyncSandbox")
async def test_e2b_backend_python_execution(mock_async_sandbox: MagicMock) -> None:
    # Set up mocks
    mock_sandbox_instance = MagicMock()
    mock_async_sandbox.create = AsyncMock(return_value=mock_sandbox_instance)

    mock_sandbox_instance.files.write_files = AsyncMock()
    mock_sandbox_instance.files.write = AsyncMock()
    mock_sandbox_instance.files.remove = AsyncMock()
    mock_sandbox_instance.sandbox_id = "test-sandbox-id"

    mock_result = MagicMock()
    mock_result.stdout = "python result"
    mock_result.stderr = ""
    mock_result.exit_code = 0
    mock_sandbox_instance.commands.run = AsyncMock(return_value=mock_result)

    with tempfile.TemporaryDirectory() as tmpdir:
        backend = E2BTerminalBackend(workspace_dir=tmpdir, api_key="dummy-key")

        res = await backend.execute_python("print('test')", env={"ENV_VAR": "value"})

        # Verify write script was called
        mock_sandbox_instance.files.write.assert_called_once()
        write_args = mock_sandbox_instance.files.write.call_args[0]
        assert write_args[0].startswith("/tmp/run_")  # noqa: S108
        assert write_args[0].endswith(".py")
        assert write_args[1] == "print('test')"

        # Verify command run had environment prefix
        mock_sandbox_instance.commands.run.assert_called_once()
        cmd_run_arg = mock_sandbox_instance.commands.run.call_args[0][0]
        assert cmd_run_arg.startswith("ENV_VAR=value python3 /tmp/run_")

        # Verify script cleanup was called
        mock_sandbox_instance.files.remove.assert_called_once_with(write_args[0])

        assert res["exit_code"] == 0
        assert res["stdout"] == "python result"


@pytest.mark.asyncio
@patch("amberclaw.terminal.e2b.AsyncSandbox")
async def test_e2b_backend_timeout_handling(mock_async_sandbox: MagicMock) -> None:
    mock_sandbox_instance = MagicMock()
    mock_async_sandbox.create = AsyncMock(return_value=mock_sandbox_instance)

    mock_sandbox_instance.files.write_files = AsyncMock()
    mock_sandbox_instance.sandbox_id = "test-sandbox-id"

    # Mock commands.run to raise TimeoutException
    mock_sandbox_instance.commands.run = AsyncMock(
        side_effect=TimeoutException("command timed out")
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        backend = E2BTerminalBackend(workspace_dir=tmpdir, api_key="dummy-key")
        res = await backend.execute_bash("sleep 10", timeout=2)

        assert res["exit_code"] == -9  # noqa: PLR2004
        assert "Timeout Error" in res["stderr"]


@pytest.mark.asyncio
@patch("amberclaw.terminal.e2b.AsyncSandbox")
async def test_e2b_backend_command_failure(mock_async_sandbox: MagicMock) -> None:
    mock_sandbox_instance = MagicMock()
    mock_async_sandbox.create = AsyncMock(return_value=mock_sandbox_instance)

    mock_sandbox_instance.files.write_files = AsyncMock()
    mock_sandbox_instance.sandbox_id = "test-sandbox-id"

    # Mock commands.run to raise CommandExitException
    mock_sandbox_instance.commands.run = AsyncMock(
        side_effect=CommandExitException(
            stderr="command not found", stdout="", exit_code=127, error="exit code 127"
        )
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        backend = E2BTerminalBackend(workspace_dir=tmpdir, api_key="dummy-key")
        res = await backend.execute_bash("invalid_command")

        assert res["exit_code"] == 127  # noqa: PLR2004
        assert res["stderr"] == "command not found"


@pytest.mark.asyncio
@patch("amberclaw.terminal.e2b.AsyncSandbox")
async def test_e2b_backend_close_and_reconnect(mock_async_sandbox: MagicMock) -> None:
    mock_sandbox_instance = MagicMock()
    mock_async_sandbox.create = AsyncMock(return_value=mock_sandbox_instance)

    mock_sandbox_instance.kill = AsyncMock()
    mock_sandbox_instance.sandbox_id = "test-sandbox-id"

    with tempfile.TemporaryDirectory() as tmpdir:
        backend = E2BTerminalBackend(workspace_dir=tmpdir, api_key="dummy-key")

        # Trigger connection
        await backend.connect()
        assert backend.sandbox is not None

        # Close connection
        await backend.close()
        mock_sandbox_instance.kill.assert_called_once()
        assert backend.sandbox is None
