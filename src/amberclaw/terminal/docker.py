import asyncio
import logging
import time
import uuid
from pathlib import Path
from typing import Any

from amberclaw.terminal.base import BaseTerminalBackend

logger = logging.getLogger(__name__)


class DockerTerminalBackend(BaseTerminalBackend):
    """Docker execution backend with strict sandbox limits (no network, cpu/mem capped)."""

    def __init__(self, workspace_dir: str, image: str = "python:3.11-slim"):
        self.workspace_dir = str(Path(workspace_dir).resolve())
        self.image = image
        self.container_name = f"amberclaw-sandbox-{uuid.uuid4().hex[:12]}"
        self.container_running = False
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the Docker container if not already running."""
        async with self._lock:
            if self.container_running:
                return

            logger.info(
                "Initializing Docker sandbox container: %s",
                self.container_name,
            )

            # Check if docker is installed
            try:
                proc = await asyncio.create_subprocess_exec(
                    "docker",
                    "--version",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.wait()
                if proc.returncode != 0:
                    raise RuntimeError(
                        "Docker CLI not available or returned non-zero code."
                    )
            except Exception as e:
                raise RuntimeError(f"Docker is not available: {e}") from e

            # Pull image if not local
            pull_proc = await asyncio.create_subprocess_exec(
                "docker",
                "pull",
                self.image,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await pull_proc.wait()

            # Run container in background
            # - Network: none
            # - Limits: 512MB RAM, 1.0 CPU
            # - Vol: mount workspace to /workspace
            # - Read-only rootfs with tmpfs for /tmp
            # - Security: Drop all capabilities, run as non-root user (1000:1000)
            run_cmd = [
                "docker",
                "run",
                "-d",
                "--name",
                self.container_name,
                "--network",
                "none",
                "--memory",
                "512m",
                "--cpus",
                "1.0",
                "--read-only",
                "--security-opt=no-new-privileges",
                "-v",
                f"{self.workspace_dir}:/workspace",
                "-w",
                "/workspace",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=64m",  # noqa: S108
                "--cap-drop=ALL",
                "--user",
                "1000:1000",
                self.image,
                "tail",
                "-f",
                "/dev/null",
            ]

            proc = await asyncio.create_subprocess_exec(
                *run_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                err_msg = stderr.decode().strip()
                logger.error("Failed to start Docker container: %s", err_msg)
                raise RuntimeError(
                    f"Docker container start failed: {err_msg}"
                )

            self.container_running = True
            try:
                await self._validate_sandbox()
            except Exception as e:
                logger.error("Sandbox validation failed: %s. Stopping container.", e)
                await self._stop_container()
                raise

            logger.info(
                "Docker sandbox container %s started and verified successfully.",
                self.container_name,
            )

    async def _stop_container(self) -> None:
        """Stop and remove the Docker container without acquiring the lock."""
        if not self.container_running:
            return

        logger.info(
            "Cleaning up Docker sandbox container: %s",
            self.container_name,
        )

        # Stop container
        stop_proc = await asyncio.create_subprocess_exec(
            "docker",
            "stop",
            "-t",
            "2",
            self.container_name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await stop_proc.wait()

        # Remove container
        rm_proc = await asyncio.create_subprocess_exec(
            "docker",
            "rm",
            "-f",
            self.container_name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await rm_proc.wait()

        self.container_running = False
        logger.info(
            "Docker sandbox container %s stopped and removed.",
            self.container_name,
        )

    async def stop(self) -> None:
        """Stop and remove the Docker container."""
        async with self._lock:
            await self._stop_container()

    async def execute_bash(
        self, command: str, timeout: int = 30
    ) -> dict[str, Any]:
        """Execute a bash command in the Docker container."""
        if not self.container_running:
            await self.start()

        start_time = time.perf_counter()
        exec_cmd = ["docker", "exec", "-i", self.container_name, "bash", "-s"]

        try:
            proc = await asyncio.create_subprocess_exec(
                *exec_cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=command.encode()),
                    timeout=timeout,
                )
                exit_code = (
                    proc.returncode if proc.returncode is not None else -1
                )
            except TimeoutError:
                # Timeout occurred, terminate/kill the exec process
                try:
                    proc.terminate()
                    await proc.wait()
                except Exception as ex:
                    logger.debug("Failed to terminate subprocess: %s", ex)
                stdout, stderr = b"", b"\nTimeout Error: Exceeded limits."
                exit_code = -9
        except Exception as e:
            stdout, stderr = b"", f"Execution error: {e}".encode()
            exit_code = -1

        execution_time_ms = (time.perf_counter() - start_time) * 1000

        return {
            "stdout": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
            "exit_code": exit_code,
            "execution_time_ms": execution_time_ms,
        }

    async def execute_python(
        self,
        code: str,
        timeout: int = 30,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute Python code in the Docker container."""
        if not self.container_running:
            await self.start()

        start_time = time.perf_counter()

        exec_cmd = ["docker", "exec", "-i"]
        if env:
            for k, v in env.items():
                exec_cmd.extend(["-e", f"{k}={v}"])
        exec_cmd.extend([self.container_name, "python", "-"])

        try:
            proc = await asyncio.create_subprocess_exec(
                *exec_cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=code.encode()),
                    timeout=timeout,
                )
                exit_code = (
                    proc.returncode if proc.returncode is not None else -1
                )
            except TimeoutError:
                try:
                    proc.terminate()
                    await proc.wait()
                except Exception as ex:
                    logger.debug("Failed to terminate subprocess: %s", ex)
                stdout, stderr = b"", b"\nTimeout Error: Exceeded limits."
                exit_code = -9
        except Exception as e:
            stdout, stderr = b"", f"Execution error: {e}".encode()
            exit_code = -1

        execution_time_ms = (time.perf_counter() - start_time) * 1000

        return {
            "stdout": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
            "exit_code": exit_code,
            "execution_time_ms": execution_time_ms,
        }

    async def _validate_sandbox(self) -> None:
        """Verify that the container enforces all required security boundaries."""
        # 1. Read-only rootfs check
        # We try to create a file at /insecure_write. This should fail.
        write_code = (
            "import sys\n"
            "try:\n"
            "    with open('/insecure_write', 'w') as f:\n"
            "        f.write('insecure')\n"
            "    sys.exit(1)\n"
            "except OSError:\n"
            "    # Expecting Read-only file system error\n"
            "    sys.exit(0)\n"
        )
        res_write = await self.execute_python(write_code, timeout=5)
        if res_write["exit_code"] != 0:
            raise RuntimeError(
                "Sandbox Validation Failed: Root filesystem is writable (expected read-only rootfs)."
            )

        # 2. Dropped Capabilities and NoNewPrivs checks
        # We read /proc/self/status and inspect CapEff, CapBnd, and NoNewPrivs.
        proc_code = (
            "import sys\n"
            "try:\n"
            "    with open('/proc/self/status', 'r') as f:\n"
            "        content = f.read()\n"
            "    lines = [line.strip() for line in content.split('\\n') if line.strip()]\n"
            "    status = {}\n"
            "    for line in lines:\n"
            "        if ':' not in line: continue\n"
            "        k, v = line.split(':', 1)\n"
            "        status[k.strip()] = v.strip()\n"
            "    \n"
            "    # Check NoNewPrivs\n"
            "    no_new_privs = status.get('NoNewPrivs', '0')\n"
            "    if no_new_privs != '1':\n"
            "        sys.exit(2)\n"
            "    \n"
            "    # Check Capabilities\n"
            "    # If all capabilities are dropped, CapEff and CapBnd should be all zeros.\n"
            "    cap_eff = int(status.get('CapEff', '0'), 16)\n"
            "    cap_bnd = int(status.get('CapBnd', '0'), 16)\n"
            "    if cap_eff != 0 or cap_bnd != 0:\n"
            "        sys.exit(3)\n"
            "    \n"
            "    sys.exit(0)\n"
            "except Exception:\n"
            "    sys.exit(4)\n"
        )
        res_proc = await self.execute_python(proc_code, timeout=5)
        if res_proc["exit_code"] != 0:
            err_code = res_proc["exit_code"]
            err_no_new_privs = 2
            err_caps_not_dropped = 3
            if err_code == err_no_new_privs:
                msg = "no-new-privileges option is not active."
            elif err_code == err_caps_not_dropped:
                msg = "capabilities are not fully dropped."
            else:
                msg = f"failed to read/parse /proc/self/status. Output: {res_proc['stderr']}"
            raise RuntimeError(f"Sandbox Validation Failed: {msg}")

    def __del__(self) -> None:
        # Destructor tries to run async task to clean up container
        if self.container_running:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    self._cleanup_task = loop.create_task(self.stop())
                else:
                    loop.run_until_complete(self.stop())
            except Exception as ex:
                logger.debug("GC cleanup failed: %s", ex)
