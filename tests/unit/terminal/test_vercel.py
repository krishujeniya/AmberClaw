from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from amberclaw.terminal.factory import BackendFactory
from amberclaw.terminal.vercel import VercelTerminalBackend


@pytest.mark.asyncio
async def test_vercel_connect_success() -> None:
    """Test successful sandbox initialization/connection."""
    mock_sandbox = AsyncMock()
    mock_sandbox.sandbox_id = "test-sandbox-id"

    with patch("vercel.sandbox.AsyncSandbox.create", return_value=mock_sandbox) as mock_create:
        backend = VercelTerminalBackend(
            workspace_dir="/dummy/workspace",
            runtime="python3.13",
            token="test-token",  # noqa: S106
            project_id="test-project",
            team_id="test-team",
            sandbox_timeout_ms=100_000,
        )
        await backend.connect()

        assert backend._connected is True
        assert backend.sandbox == mock_sandbox
        mock_create.assert_called_once_with(
            runtime="python3.13",
            token="test-token",  # noqa: S106
            project_id="test-project",
            team_id="test-team",
            timeout=100_000,
        )


@pytest.mark.asyncio
async def test_vercel_connect_error() -> None:
    """Test connection error propagating correctly."""
    with patch("vercel.sandbox.AsyncSandbox.create", side_effect=Exception("API Error")):
        backend = VercelTerminalBackend(workspace_dir="/dummy/workspace")
        with pytest.raises(Exception, match="API Error"):
            await backend.connect()

        assert backend._connected is False
        assert backend.sandbox is None


@pytest.mark.asyncio
async def test_vercel_close() -> None:
    """Test stopping and cleaning up the sandbox connection."""
    mock_sandbox = AsyncMock()
    mock_sandbox.sandbox_id = "test-sandbox-id"

    backend = VercelTerminalBackend(workspace_dir="/dummy/workspace")
    backend.sandbox = mock_sandbox
    backend._connected = True
    backend._created_dirs.add("some_dir")
    backend._synced_files["some_file"] = "hash"

    await backend.close()

    assert backend._connected is False
    assert backend.sandbox is None
    assert len(backend._created_dirs) == 0
    assert len(backend._synced_files) == 0
    mock_sandbox.stop.assert_called_once()


@pytest.mark.asyncio
async def test_vercel_sync_workspace() -> None:
    """Test directory detection, remote creation, and file uploads."""
    mock_sandbox = AsyncMock()

    with patch("vercel.sandbox.AsyncSandbox.create", return_value=mock_sandbox), \
         patch("os.walk") as mock_walk, \
         patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.open") as mock_open, \
         patch("amberclaw.terminal.vercel.VercelTerminalBackend._get_file_hash", return_value="dummy_hash"):

        # Mock directory structure: 1 nested file
        mock_walk.return_value = [("/dummy/workspace", [], ["sub/file.txt"])]

        # Mock file hash check
        mock_file = MagicMock()
        mock_file.read.return_value = b"file contents"
        mock_open.return_value.__enter__.return_value = mock_file

        backend = VercelTerminalBackend(workspace_dir="/dummy/workspace")
        await backend._sync_workspace()

        # Check directories are created (subdir "sub" of "sub/file.txt")
        mock_sandbox.mk_dir.assert_called_once_with("sub")
        # Check files are uploaded
        mock_sandbox.write_files.assert_called_once_with([
            {
                "path": "sub/file.txt",
                "content": b"file contents",
            }
        ])


@pytest.mark.asyncio
async def test_vercel_execute_bash() -> None:
    """Test executing a remote bash command and getting results."""
    mock_finished = AsyncMock()
    mock_finished.exit_code = 0
    mock_finished.stdout.return_value = "hello stdout"
    mock_finished.stderr.return_value = ""

    mock_cmd = AsyncMock()
    mock_cmd.wait.return_value = mock_finished

    mock_sandbox = AsyncMock()
    mock_sandbox.run_command_detached.return_value = mock_cmd

    with patch("vercel.sandbox.AsyncSandbox.create", return_value=mock_sandbox), \
         patch("amberclaw.terminal.vercel.VercelTerminalBackend._sync_workspace", new_callable=AsyncMock):

        backend = VercelTerminalBackend(workspace_dir="/dummy/workspace")
        backend.sandbox = mock_sandbox
        backend._connected = True
        result = await backend.execute_bash("echo 'hello'", timeout=10)

        assert result["stdout"] == "hello stdout"
        assert result["stderr"] == ""
        assert result["exit_code"] == 0
        assert "execution_time_ms" in result
        mock_sandbox.run_command_detached.assert_called_once_with("bash", ["-c", "echo 'hello'"])


@pytest.mark.asyncio
async def test_vercel_execute_python() -> None:
    """Test writing code block and running python remote execution."""
    mock_finished = AsyncMock()
    mock_finished.exit_code = 0
    mock_finished.stdout.return_value = "py success"
    mock_finished.stderr.return_value = ""

    mock_cmd = AsyncMock()
    mock_cmd.wait.return_value = mock_finished

    mock_sandbox = AsyncMock()
    mock_sandbox.run_command_detached.return_value = mock_cmd

    with patch("vercel.sandbox.AsyncSandbox.create", return_value=mock_sandbox), \
         patch("amberclaw.terminal.vercel.VercelTerminalBackend._sync_workspace", new_callable=AsyncMock):

        backend = VercelTerminalBackend(workspace_dir="/dummy/workspace")
        backend.sandbox = mock_sandbox
        backend._connected = True
        result = await backend.execute_python("print('hello')", timeout=15, env={"X": "1"})

        assert result["stdout"] == "py success"
        assert result["exit_code"] == 0
        # Verify it uploaded the python script and executed it
        mock_sandbox.write_files.assert_called_once()
        mock_sandbox.run_command_detached.assert_called_once()
        args = mock_sandbox.run_command_detached.call_args[0]
        kwargs = mock_sandbox.run_command_detached.call_args[1]
        assert args[0] == "python3"
        assert args[1][0].startswith("_amberclaw_")
        assert kwargs["env"] == {"X": "1"}


@pytest.mark.asyncio
async def test_vercel_timeout_handling() -> None:
    """Test that command timeout is correctly killed and returns exit_code -9."""
    mock_cmd = AsyncMock()
    # Mock cmd.wait to raise TimeoutError wrapped under asyncio.wait_for
    mock_cmd.wait.side_effect = TimeoutError()

    mock_sandbox = AsyncMock()
    mock_sandbox.run_command_detached.return_value = mock_cmd

    with patch("vercel.sandbox.AsyncSandbox.create", return_value=mock_sandbox), \
         patch("amberclaw.terminal.vercel.VercelTerminalBackend._sync_workspace", new_callable=AsyncMock):

        backend = VercelTerminalBackend(workspace_dir="/dummy/workspace")
        backend.sandbox = mock_sandbox
        backend._connected = True
        result = await backend.execute_bash("sleep 100", timeout=1)

        assert result["exit_code"] == -9  # noqa: PLR2004
        assert "Timeout Error" in result["stderr"]
        mock_cmd.kill.assert_called_once()


@pytest.mark.asyncio
async def test_factory_vercel_instantiation() -> None:
    """Test BackendFactory returns a correct VercelTerminalBackend instance."""
    backend = BackendFactory.create_backend(
        backend_type="vercel",
        workspace_dir="/dummy/workspace",
        runtime="python3.12",
        token="some-token",  # noqa: S106
        project_id="pid",
        team_id="tid",
        sandbox_timeout_ms=5000,
    )

    assert isinstance(backend, VercelTerminalBackend)
    assert backend.workspace_dir == "/dummy/workspace"
    assert backend.runtime == "python3.12"
    assert backend.token == "some-token"  # noqa: S105
    assert backend.project_id == "pid"
    assert backend.team_id == "tid"
    assert backend.sandbox_timeout_ms == 5000  # noqa: PLR2004
