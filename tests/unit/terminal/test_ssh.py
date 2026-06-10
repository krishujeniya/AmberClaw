import socket
from unittest.mock import MagicMock, patch

import pytest

from amberclaw.terminal.factory import BackendFactory
from amberclaw.terminal.ssh import SSHTerminalBackend


@pytest.mark.asyncio
async def test_ssh_backend_execution_success() -> None:
    mock_client = MagicMock()
    mock_transport = MagicMock()
    mock_channel = MagicMock()

    mock_client.get_transport.return_value = mock_transport
    mock_transport.is_active.return_value = True
    mock_transport.open_session.return_value = mock_channel

    # A simple state tracker for our mock channel to avoid StopIteration issues
    ready_state = {"stdout": True, "stderr": True, "exit": False}

    def mock_recv_ready() -> bool:
        if ready_state["stdout"]:
            ready_state["stdout"] = False
            return True
        return False

    def mock_recv_stderr_ready() -> bool:
        if ready_state["stderr"]:
            ready_state["stderr"] = False
            return True
        return False

    def mock_exit_status_ready() -> bool:
        if not ready_state["stdout"] and not ready_state["stderr"]:
            ready_state["exit"] = True
        return ready_state["exit"]

    mock_channel.recv_ready.side_effect = mock_recv_ready
    mock_channel.recv_stderr_ready.side_effect = mock_recv_stderr_ready
    mock_channel.exit_status_ready.side_effect = mock_exit_status_ready
    mock_channel.recv.return_value = b"stdout response"
    mock_channel.recv_stderr.return_value = b"stderr response"
    mock_channel.recv_exit_status.return_value = 0

    with patch("paramiko.SSHClient", return_value=mock_client):
        backend = SSHTerminalBackend(
            host="1.2.3.4",
            port=2222,
            username="testuser",
            password="testpassword",
            workspace_dir="/remote/workspace",
        )

        result = await backend.execute_bash("echo 'hello'", timeout=10)

        # Verify connect options
        mock_client.connect.assert_called_once_with(
            hostname="1.2.3.4",
            port=2222,
            username="testuser",
            password="testpassword",
            key_filename=None,
            allow_agent=True,
        )

        # Verify workspace prepending
        mock_channel.exec_command.assert_called_once_with(
            "cd /remote/workspace && echo 'hello'"
        )

        # Assert result extraction
        assert result["exit_code"] == 0
        assert result["stdout"] == "stdout response"
        assert result["stderr"] == "stderr response"


@pytest.mark.asyncio
async def test_ssh_backend_execute_python() -> None:
    mock_client = MagicMock()
    mock_transport = MagicMock()
    mock_channel = MagicMock()

    mock_client.get_transport.return_value = mock_transport
    mock_transport.is_active.return_value = True
    mock_transport.open_session.return_value = mock_channel

    mock_channel.exit_status_ready.return_value = True
    mock_channel.recv_ready.return_value = False
    mock_channel.recv_stderr_ready.return_value = False
    mock_channel.recv_exit_status.return_value = 0

    with patch("paramiko.SSHClient", return_value=mock_client):
        backend = SSHTerminalBackend(host="1.2.3.4", username="testuser")

        code = "print('hello')"
        env = {"TEST_VAR": "value", "ANOTHER_VAR": "value2"}
        await backend.execute_python(code, env=env)

        # Verify environment variables exported and stdin written
        exec_call_arg = mock_channel.exec_command.call_args[0][0]
        assert "export TEST_VAR=value" in exec_call_arg
        assert "export ANOTHER_VAR=value2" in exec_call_arg
        assert "python3 -" in exec_call_arg

        mock_channel.sendall.assert_called_once_with(code)


@pytest.mark.asyncio
async def test_ssh_backend_timeout() -> None:
    mock_client = MagicMock()
    mock_transport = MagicMock()
    mock_channel = MagicMock()

    mock_client.get_transport.return_value = mock_transport
    mock_transport.is_active.return_value = True
    mock_transport.open_session.return_value = mock_channel

    # Simulate socket timeout during execution
    mock_channel.exec_command.side_effect = socket.timeout("Command timed out")

    with patch("paramiko.SSHClient", return_value=mock_client):
        backend = SSHTerminalBackend(host="1.2.3.4", username="testuser")
        result = await backend.execute_bash("sleep 10", timeout=2)

        assert result["exit_code"] == -9
        stderr_lower = result["stderr"].lower()
        assert "timeout" in stderr_lower or "timed out" in stderr_lower


def test_backend_factory() -> None:
    # Local backend instantiation
    local_backend = BackendFactory.create_backend("local", workspace_dir="/tmp/ws")
    from amberclaw.terminal.local import LocalTerminalBackend

    assert isinstance(local_backend, LocalTerminalBackend)

    # Docker backend instantiation
    docker_backend = BackendFactory.create_backend(
        "docker", workspace_dir="/tmp/ws", image="python:3.11-alpine"
    )
    from amberclaw.terminal.docker import DockerTerminalBackend

    assert isinstance(docker_backend, DockerTerminalBackend)
    assert docker_backend.image == "python:3.11-alpine"

    # SSH backend instantiation
    ssh_backend = BackendFactory.create_backend(
        "ssh", workspace_dir="/tmp/ws", host="myhost", username="user"
    )

    assert isinstance(ssh_backend, SSHTerminalBackend)
    assert ssh_backend.host == "myhost"
    assert ssh_backend.username == "user"

    # Invalid backend type raises ValueError
    with pytest.raises(ValueError, match="Unknown terminal backend type"):
        BackendFactory.create_backend("invalid_type", workspace_dir="/tmp/ws")
