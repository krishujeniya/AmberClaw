import asyncio
import logging
import shutil
import time
from pathlib import Path
from typing import Any

from amberclaw.terminal.base import BaseTerminalBackend

logger = logging.getLogger(__name__)


class SingularityTerminalBackend(BaseTerminalBackend):
    """Singularity / Apptainer execution backend with isolated user namespaces."""

    def __init__(
        self,
        workspace_dir: str,
        image: str = "docker://python:3.11-slim",
    ):
        self.workspace_dir = str(Path(workspace_dir).resolve())
        self.image = image
        self._binary = self._resolve_binary()

    def _resolve_binary(self) -> str:
        """Resolve the Apptainer or Singularity executable on the host system."""
        if shutil.which("apptainer"):
            return "apptainer"
        if shutil.which("singularity"):
            return "singularity"
        
        logger.warning(
            "Neither 'apptainer' nor 'singularity' was found in PATH. Defaulting to 'singularity'."
        )
        return "singularity"

    def _build_exec_command(self) -> list[str]:
        """Build the common singularity/apptainer exec command prefix."""
        return [
            self._binary,
            "exec",
            "--containall",
            "--no-home",
            "--cleanenv",
            "-B",
            f"{self.workspace_dir}:/workspace",
            "--pwd",
            "/workspace",
            self.image,
        ]

    def _build_env(self, custom_env: dict[str, str] | None) -> dict[str, str]:
        """Format environment variables for Singularity/Apptainer propagation."""
        env: dict[str, str] = {}
        if not custom_env:
            return env

        for k, v in custom_env.items():
            # Support both singularity and apptainer prefixes for maximum compatibility
            env[f"SINGULARITYENV_{k}"] = v
            env[f"APPTAINERENV_{k}"] = v
        return env

    async def execute_bash(
        self, command: str, timeout: int = 30
    ) -> dict[str, Any]:
        """Execute a bash command transiently inside the container."""
        start_time = time.perf_counter()
        
        exec_cmd = [*self._build_exec_command(), "bash", "-s"]

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
        """Execute Python code transiently inside the container."""
        start_time = time.perf_counter()

        exec_cmd = [*self._build_exec_command(), "python", "-"]
        sub_env = self._build_env(env)

        try:
            # We pass environment variables using the system environment prefix mapping
            proc = await asyncio.create_subprocess_exec(
                *exec_cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=sub_env if sub_env else None,
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
