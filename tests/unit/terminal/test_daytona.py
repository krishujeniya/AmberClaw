from unittest.mock import MagicMock, patch

import pytest
from daytona import (
    CodeRunParams,
    Daytona,
)

from amberclaw.terminal.daytona import DaytonaTerminalBackend
from amberclaw.terminal.factory import BackendFactory


class MockExecuteResponse:
    """Mock structure for Daytona process execution responses."""

    def __init__(self, result: str, exit_code: int = 0, stderr: str = ""):
        self.result = result
        self.exit_code = exit_code
        self.stderr = stderr
        self.artifacts = MagicMock()
        self.artifacts.stderr = stderr


@pytest.fixture
def mock_sandbox() -> MagicMock:
    """Mock for the Daytona Sandbox object."""
    sandbox = MagicMock()
    sandbox.id = "test-sandbox-123"
    
    # Setup mock exec response
    sandbox.process.exec.return_value = MockExecuteResponse(
        result="hello from bash", exit_code=0
    )
    
    # Setup mock code_run response
    sandbox.process.code_run.return_value = MockExecuteResponse(
        result="hello from python", exit_code=0
    )
    
    return sandbox


@pytest.fixture
def mock_daytona_client(mock_sandbox: MagicMock) -> MagicMock:
    """Mock for the Daytona client."""
    client = MagicMock(spec=Daytona)
    client.create.return_value = mock_sandbox
    return client


@pytest.mark.asyncio
async def test_daytona_connection_lifecycle(mock_daytona_client: MagicMock, mock_sandbox: MagicMock) -> None:
    """Test connect and close lifecycle of Daytona backend."""
    with patch("amberclaw.terminal.daytona.Daytona", return_value=mock_daytona_client), \
         patch("amberclaw.terminal.daytona.DaytonaConfig") as mock_config_cls:
         
        backend = DaytonaTerminalBackend(
            workspace_dir="/workspace",
            api_key="test-key",
            api_url="https://api.test.daytona.io",
            target="us",
            create_kwargs={"image": "custom-image"}
        )

        # Assert no connection initially
        assert backend.client is None
        assert backend.sandbox is None

        # Connect
        await backend.connect()
        
        # Verify Config & Client instantiation
        mock_config_cls.assert_called_once_with(
            api_key="test-key",
            api_url="https://api.test.daytona.io",
            target="us"
        )
        mock_daytona_client.create.assert_called_once_with(image="custom-image")
        assert backend.client == mock_daytona_client
        assert backend.sandbox == mock_sandbox

        # Disconnect
        await backend.close()
        mock_sandbox.close.assert_called_once()
        assert backend.sandbox is None
        assert backend.client is None


@pytest.mark.asyncio
async def test_daytona_execute_bash(mock_daytona_client: MagicMock, mock_sandbox: MagicMock) -> None:
    """Test bash execution in Daytona sandbox."""
    with patch("amberclaw.terminal.daytona.Daytona", return_value=mock_daytona_client):
        backend = DaytonaTerminalBackend(workspace_dir="/workspace")

        result = await backend.execute_bash("echo 'hello'", timeout=15)

        # Verify command execution details
        mock_sandbox.process.exec.assert_called_once_with(
            command="echo 'hello'",
            cwd="/workspace",
            timeout=15,
        )

        assert result["stdout"] == "hello from bash"
        assert result["stderr"] == ""
        assert result["exit_code"] == 0
        assert result["execution_time_ms"] > 0


@pytest.mark.asyncio
async def test_daytona_execute_python(mock_daytona_client: MagicMock, mock_sandbox: MagicMock) -> None:
    """Test python code execution in Daytona sandbox."""
    with patch("amberclaw.terminal.daytona.Daytona", return_value=mock_daytona_client):
        backend = DaytonaTerminalBackend(workspace_dir="/workspace")
        env_vars = {"DEBUG": "1"}

        result = await backend.execute_python(
            "print('hello')",
            timeout=20,
            env=env_vars,
        )

        # Verify code run details
        _, kwargs = mock_sandbox.process.code_run.call_args
        assert kwargs["code"] == "print('hello')"
        assert kwargs["timeout"] == 20  # noqa: PLR2004
        assert isinstance(kwargs["params"], CodeRunParams)
        assert kwargs["params"].env == env_vars

        assert result["stdout"] == "hello from python"
        assert result["stderr"] == ""
        assert result["exit_code"] == 0


@pytest.mark.asyncio
async def test_daytona_execution_exception_mapping(mock_daytona_client: MagicMock, mock_sandbox: MagicMock) -> None:
    """Test exception and timeout mapping in execution."""
    with patch("amberclaw.terminal.daytona.Daytona", return_value=mock_daytona_client):
        backend = DaytonaTerminalBackend(workspace_dir="/workspace")

        # Simulate standard error exception
        mock_sandbox.process.exec.side_effect = Exception("General error")
        result = await backend.execute_bash("exit 1")
        assert result["exit_code"] == -1
        assert "General error" in result["stderr"]

        # Simulate timeout exception
        mock_sandbox.process.exec.side_effect = TimeoutError("Command timed out")
        result = await backend.execute_bash("sleep 100")
        assert result["exit_code"] == -9  # noqa: PLR2004
        assert "Command timed out" in result["stderr"]


@pytest.mark.asyncio
async def test_factory_daytona_instantiation(mock_daytona_client: MagicMock) -> None:
    """Test instantiating Daytona backend from BackendFactory."""
    with patch("amberclaw.terminal.daytona.Daytona", return_value=mock_daytona_client):
        backend = BackendFactory.create_backend(
            backend_type="daytona",
            workspace_dir="/workspace",
            api_key="api-key",
            api_url="api-url",
            target="target",
            create_kwargs={"image": "img"}
        )

        assert isinstance(backend, DaytonaTerminalBackend)
        assert backend.workspace_dir == "/workspace"
        assert backend.api_key == "api-key"
        assert backend.api_url == "api-url"
        assert backend.target == "target"
        assert backend.create_kwargs == {"image": "img"}
