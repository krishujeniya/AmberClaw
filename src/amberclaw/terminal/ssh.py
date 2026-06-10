# ruff: noqa: PLC0415
import asyncio
import contextlib
import logging
import shlex
import socket
import time
from typing import Any

import paramiko  # type: ignore[import-untyped]

from amberclaw.terminal.base import BaseTerminalBackend

logger = logging.getLogger(__name__)


class SSHTerminalBackend(BaseTerminalBackend):
    """SSH execution backend that runs bash and Python commands on a remote system."""

    def __init__(  # noqa: PLR0913
        self,
        workspace_dir: str | None = None,
        host: str = "localhost",
        port: int = 22,
        username: str = "root",
        password: str | None = None,
        key_filename: str | None = None,
        agent_forwarding: bool = True,
    ):
        self.workspace_dir = workspace_dir
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.agent_forwarding = agent_forwarding
        self.client: paramiko.SSHClient | None = None
        self._lock = asyncio.Lock()

    def _connect_sync(self) -> None:
        """Establish the SSH connection synchronously. Must be run in an executor thread."""
        if self.client is not None:
            transport = self.client.get_transport()
            if transport and transport.is_active():
                return
            self._close_sync()

        logger.info("Connecting to remote host %s:%d via SSH...", self.host, self.port)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # noqa: S507

        try:
            client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                key_filename=self.key_filename,
                allow_agent=self.agent_forwarding,
            )
            self.client = client
            logger.info("SSH connection established successfully to %s:%d", self.host, self.port)
        except Exception as e:
            logger.error("Failed to connect to %s:%d via SSH: %s", self.host, self.port, e)
            raise

    def _close_sync(self) -> None:
        """Close the SSH connection synchronously. Must be run in an executor thread."""
        if self.client:
            with contextlib.suppress(Exception):
                self.client.close()
            self.client = None

    async def connect(self) -> None:
        """Asynchronously establish the SSH connection."""
        async with self._lock:
            await asyncio.to_thread(self._connect_sync)

    async def close(self) -> None:
        """Asynchronously close the SSH connection."""
        async with self._lock:
            await asyncio.to_thread(self._close_sync)

    def _execute_command_sync(  # noqa: PLR0912, PLR0915
        self, command: str, stdin_data: str | None = None, timeout: int = 30
    ) -> dict[str, Any]:
        """Execute command synchronously over SSH. Must be run in an executor thread."""
        self._connect_sync()
        if not self.client:
            raise RuntimeError("SSH client not connected.")

        start_time = time.perf_counter()

        transport = self.client.get_transport()
        if not transport:
            raise RuntimeError("SSH transport is not available.")

        chan = transport.open_session()
        chan.settimeout(float(timeout))

        if self.agent_forwarding:
            try:
                from paramiko.agent import (  # type: ignore[import-untyped]
                    AgentRequestHandler,
                )
                AgentRequestHandler(chan)
            except Exception as e:
                logger.debug("Could not start AgentRequestHandler: %s", e)

        # Prepend directory context if workspace_dir is specified
        if self.workspace_dir:
            command = f"cd {shlex.quote(self.workspace_dir)} && {command}"

        stdout_chunks = []
        stderr_chunks = []
        exit_code = -1

        try:
            logger.debug("Executing remote command via SSH: %s", command)
            chan.exec_command(command)

            if stdin_data:
                chan.sendall(stdin_data)
                chan.shutdown_write()

            # Poll for stdout/stderr data or channel exit readiness
            while not chan.exit_status_ready() or chan.recv_ready() or chan.recv_stderr_ready():
                if chan.recv_ready():
                    data = chan.recv(4096)
                    if data:
                        stdout_chunks.append(data)
                if chan.recv_stderr_ready():
                    data = chan.recv_stderr(4096)
                    if data:
                        stderr_chunks.append(data)
                if not chan.recv_ready() and not chan.recv_stderr_ready():
                    time.sleep(0.01)

            exit_code = chan.recv_exit_status()

            # Drain any remaining bytes
            while chan.recv_ready():
                data = chan.recv(4096)
                if data:
                    stdout_chunks.append(data)
            while chan.recv_stderr_ready():
                data = chan.recv_stderr(4096)
                if data:
                    stderr_chunks.append(data)
        except Exception as e:
            logger.warning("SSH command execution encountered an exception: %s", e)
            is_timeout = (
                isinstance(e, (TimeoutError, socket.timeout))
                or "timeout" in str(e).lower()
                or "timed out" in str(e).lower()
            )
            exit_code = -9 if is_timeout else -1
            stderr_chunks.append(f"\nExecution error: {e}".encode())

        execution_time_ms = (time.perf_counter() - start_time) * 1000

        return {
            "stdout": b"".join(stdout_chunks).decode("utf-8", errors="replace"),
            "stderr": b"".join(stderr_chunks).decode("utf-8", errors="replace"),
            "exit_code": exit_code,
            "execution_time_ms": execution_time_ms,
        }

    async def execute_bash(self, command: str, timeout: int = 30) -> dict[str, Any]:
        """Asynchronously execute a bash command on the remote system."""
        try:
            return await asyncio.to_thread(self._execute_command_sync, command, None, timeout)
        except Exception as e:
            logger.error("SSH bash execution failed: %s", e)
            return {
                "stdout": "",
                "stderr": f"SSH connection/execution error: {e}",
                "exit_code": -1,
                "execution_time_ms": 0.0,
            }

    async def execute_python(
        self,
        code: str,
        timeout: int = 30,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Asynchronously execute Python code on the remote system."""
        env_cmds = []
        if env:
            for k, v in env.items():
                env_cmds.append(f"export {k}={shlex.quote(v)}")

        python_cmd = "python3 -"
        if env_cmds:
            full_command = f"{' && '.join(env_cmds)} && {python_cmd}"
        else:
            full_command = python_cmd

        try:
            return await asyncio.to_thread(self._execute_command_sync, full_command, code, timeout)
        except Exception as e:
            logger.error("SSH Python execution failed: %s", e)
            return {
                "stdout": "",
                "stderr": f"SSH connection/execution error: {e}",
                "exit_code": -1,
                "execution_time_ms": 0.0,
            }

    def __del__(self) -> None:
        if self.client:
            with contextlib.suppress(Exception):
                self.client.close()
