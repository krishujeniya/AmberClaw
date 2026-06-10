import asyncio
import contextlib
import logging
import time
from typing import Any

from daytona import (
    CodeRunParams,
    Daytona,
    DaytonaConfig,
)

from amberclaw.terminal.base import BaseTerminalBackend

logger = logging.getLogger(__name__)


class DaytonaTerminalBackend(BaseTerminalBackend):
    """Daytona execution backend that runs bash and Python commands in serverless workspaces."""

    def __init__(
        self,
        workspace_dir: str | None = None,
        api_key: str | None = None,
        api_url: str | None = None,
        target: str | None = None,
        create_kwargs: dict[str, Any] | None = None,
    ):
        self.workspace_dir = workspace_dir
        self.api_key = api_key
        self.api_url = api_url
        self.target = target
        self.create_kwargs = create_kwargs or {}
        self.client: Daytona | None = None
        self.sandbox: Any = None
        self._lock = asyncio.Lock()

    def _connect_sync(self) -> None:
        """Establish connection and initialize the Daytona sandbox. Must run in an executor."""
        if self.client is not None and self.sandbox is not None:
            return

        logger.info("Initializing Daytona client...")
        if self.api_key or self.api_url or self.target:
            config = DaytonaConfig(
                api_key=self.api_key,
                api_url=self.api_url,
                target=self.target,
            )
            self.client = Daytona(config=config)
        else:
            self.client = Daytona()

        logger.info("Creating Daytona sandbox...")
        self.sandbox = self.client.create(**self.create_kwargs)
        logger.info("Daytona sandbox created successfully with ID: %s", getattr(self.sandbox, "id", "unknown"))

    def _close_sync(self) -> None:
        """Close and delete the Daytona sandbox. Must run in an executor."""
        if self.sandbox:
            sandbox_id = getattr(self.sandbox, "id", "unknown")
            logger.info("Closing Daytona sandbox: %s", sandbox_id)
            with contextlib.suppress(Exception):
                self.sandbox.close()
            self.sandbox = None
        self.client = None

    async def connect(self) -> None:
        """Asynchronously connect and spin up the Daytona sandbox."""
        async with self._lock:
            await asyncio.to_thread(self._connect_sync)

    async def close(self) -> None:
        """Asynchronously close and clean up the Daytona sandbox."""
        async with self._lock:
            await asyncio.to_thread(self._close_sync)

    def _execute_bash_sync(self, command: str, timeout: int = 30) -> dict[str, Any]:
        """Execute bash command synchronously in the sandbox. Must run in an executor."""
        self._connect_sync()
        if not self.sandbox:
            raise RuntimeError("Daytona sandbox is not available.")

        start_time = time.perf_counter()
        stdout = ""
        stderr = ""
        exit_code = -1

        try:
            logger.debug("Executing Daytona bash command: %s", command)
            response = self.sandbox.process.exec(
                command=command,
                cwd=self.workspace_dir,
                timeout=timeout,
            )

            if response:
                stdout = getattr(response, "result", "") or ""
                exit_code = getattr(response, "exit_code", 0)
                if exit_code is None:
                    exit_code = 0
                
                # Check for standard errors if returned separately
                if hasattr(response, "artifacts") and response.artifacts:
                    stderr = getattr(response.artifacts, "stderr", "") or ""
                elif hasattr(response, "stderr"):
                    stderr = getattr(response, "stderr", "") or ""
        except Exception as e:
            logger.warning("Daytona bash execution encountered an exception: %s", e)
            is_timeout = (
                isinstance(e, TimeoutError)
                or "timeout" in str(e).lower()
                or "timed out" in str(e).lower()
            )
            exit_code = -9 if is_timeout else -1
            stderr = f"Execution error: {e}"

        execution_time_ms = (time.perf_counter() - start_time) * 1000

        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "execution_time_ms": execution_time_ms,
        }

    async def execute_bash(self, command: str, timeout: int = 30) -> dict[str, Any]:
        """Asynchronously execute a bash command inside the Daytona sandbox."""
        try:
            return await asyncio.to_thread(self._execute_bash_sync, command, timeout)
        except Exception as e:
            logger.error("Daytona bash execution failed: %s", e)
            return {
                "stdout": "",
                "stderr": f"Daytona connection/execution error: {e}",
                "exit_code": -1,
                "execution_time_ms": 0.0,
            }

    def _execute_python_sync(
        self,
        code: str,
        timeout: int = 30,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute Python code synchronously in the sandbox. Must run in an executor."""
        self._connect_sync()
        if not self.sandbox:
            raise RuntimeError("Daytona sandbox is not available.")

        start_time = time.perf_counter()
        stdout = ""
        stderr = ""
        exit_code = -1

        try:
            logger.debug("Executing Daytona Python code...")
            params = CodeRunParams(env=env) if env else None
            response = self.sandbox.process.code_run(
                code=code,
                params=params,
                timeout=timeout,
            )

            if response:
                stdout = getattr(response, "result", "") or ""
                exit_code = getattr(response, "exit_code", 0)
                if exit_code is None:
                    exit_code = 0

                if hasattr(response, "artifacts") and response.artifacts:
                    stderr = getattr(response.artifacts, "stderr", "") or ""
                elif hasattr(response, "stderr"):
                    stderr = getattr(response, "stderr", "") or ""
        except Exception as e:
            logger.warning("Daytona Python execution encountered an exception: %s", e)
            is_timeout = (
                isinstance(e, TimeoutError)
                or "timeout" in str(e).lower()
                or "timed out" in str(e).lower()
            )
            exit_code = -9 if is_timeout else -1
            stderr = f"Execution error: {e}"

        execution_time_ms = (time.perf_counter() - start_time) * 1000

        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "execution_time_ms": execution_time_ms,
        }

    async def execute_python(
        self,
        code: str,
        timeout: int = 30,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Asynchronously execute Python code inside the Daytona sandbox."""
        try:
            return await asyncio.to_thread(self._execute_python_sync, code, timeout, env)
        except Exception as e:
            logger.error("Daytona Python execution failed: %s", e)
            return {
                "stdout": "",
                "stderr": f"Daytona connection/execution error: {e}",
                "exit_code": -1,
                "execution_time_ms": 0.0,
            }

    def __del__(self) -> None:
        if self.sandbox:
            with contextlib.suppress(Exception):
                self.sandbox.close()
