# ruff: noqa: PLC0415
import asyncio
import hashlib
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

from amberclaw.terminal.base import BaseTerminalBackend

logger = logging.getLogger(__name__)


class VercelTerminalBackend(BaseTerminalBackend):
    """Terminal execution backend running in Vercel Sandbox (Firecracker microVM) environments."""

    def __init__(  # noqa: PLR0913
        self,
        workspace_dir: str,
        runtime: str = "python3.13",
        token: str | None = None,
        project_id: str | None = None,
        team_id: str | None = None,
        sandbox_timeout_ms: int = 300_000,
    ):
        self.workspace_dir = str(Path(workspace_dir).resolve())
        self.runtime = runtime
        self.token = token
        self.project_id = project_id
        self.team_id = team_id
        self.sandbox_timeout_ms = sandbox_timeout_ms

        self.sandbox: Any = None
        self._connected = False
        self._synced_files: dict[str, str] = {}
        self._created_dirs: set[str] = set()
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Establish connection / create the Vercel Sandbox."""
        async with self._lock:
            if self._connected and self.sandbox:
                return

            try:
                from vercel.sandbox import AsyncSandbox

                logger.info(
                    "Initializing Vercel Sandbox (runtime=%s, timeout=%dms)...",
                    self.runtime,
                    self.sandbox_timeout_ms,
                )
                self.sandbox = await AsyncSandbox.create(
                    runtime=self.runtime,
                    token=self.token,
                    project_id=self.project_id,
                    team_id=self.team_id,
                    timeout=self.sandbox_timeout_ms,
                )
                self._connected = True
                logger.info(
                    "Vercel Sandbox initialized successfully (ID: %s)",
                    self.sandbox.sandbox_id,
                )
            except Exception as e:
                logger.error("Failed to initialize Vercel Sandbox: %s", e)
                raise

    async def close(self) -> None:
        """Close and stop the active Vercel Sandbox."""
        async with self._lock:
            if self.sandbox:
                try:
                    await self.sandbox.stop()
                    logger.info(
                        "Vercel Sandbox (ID: %s) stopped successfully.",
                        self.sandbox.sandbox_id,
                    )
                except Exception as e:
                    logger.warning("Failed to stop Vercel Sandbox: %s", e)
                finally:
                    self.sandbox = None
                    self._connected = False
                    self._created_dirs.clear()
                    self._synced_files.clear()

    def _get_file_hash(self, path: Path) -> str:
        """Get SHA256 hash of a local file."""
        hasher = hashlib.sha256()
        with path.open("rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _prepare_sync_payload_sync(
        self,
    ) -> tuple[set[str], list[dict[str, Any]], dict[str, str]]:
        """Walk workspace, calculate hashes, read modified files synchronously. Runs in executor thread."""
        dirs_to_create: set[str] = set()
        files_to_upload: list[dict[str, Any]] = []
        new_synced_files = dict(self._synced_files)

        workspace_path = Path(self.workspace_dir)
        if not workspace_path.exists():
            return dirs_to_create, files_to_upload, new_synced_files

        for root, _, files in os.walk(self.workspace_dir):
            for file in files:
                local_file_path = Path(root) / file
                rel_path = local_file_path.relative_to(workspace_path)
                rel_path_str = str(rel_path)

                try:
                    file_hash = self._get_file_hash(local_file_path)
                    if self._synced_files.get(rel_path_str) != file_hash:
                        # Mark parent directories for creation
                        parent = rel_path.parent
                        if str(parent) != "." and str(parent) != "":
                            # Add all ancestor directory parts
                            parts = parent.parts
                            for i in range(1, len(parts) + 1):
                                ancestor = "/".join(parts[:i])
                                dirs_to_create.add(ancestor)

                        with local_file_path.open("rb") as f:
                            content = f.read()

                        files_to_upload.append({
                            "path": rel_path_str,
                            "content": content,
                        })
                        new_synced_files[rel_path_str] = file_hash
                except Exception as e:
                    logger.warning(
                        "Failed to prepare file %s for sync: %s",
                        rel_path_str,
                        e,
                    )

        return dirs_to_create, files_to_upload, new_synced_files

    async def _sync_workspace(self) -> None:
        """Synchronize modified local workspace files to the remote sandbox environment."""
        await self.connect()
        if not self.sandbox:
            raise RuntimeError("Vercel Sandbox is not connected.")

        # Prepare payload off of the main event loop
        dirs_to_create, files_to_upload, new_synced_files = (
            await asyncio.to_thread(self._prepare_sync_payload_sync)
        )

        # Create missing directories in the sandbox
        sorted_dirs = sorted(dirs_to_create, key=len)
        for directory in sorted_dirs:
            if directory not in self._created_dirs:
                try:
                    await self.sandbox.mk_dir(directory)
                    self._created_dirs.add(directory)
                except Exception as e:
                    logger.warning(
                        "Failed to create directory %s in Vercel Sandbox: %s",
                        directory,
                        e,
                    )

        # Upload new/modified files
        if files_to_upload:
            try:
                await self.sandbox.write_files(files_to_upload)
                self._synced_files.update(new_synced_files)
                logger.info("Successfully synced %d files to Vercel Sandbox.", len(files_to_upload))
            except Exception as e:
                logger.error("Failed to upload synced files to Vercel Sandbox: %s", e)
                raise

    async def execute_bash(
        self, command: str, timeout: int = 30
    ) -> dict[str, Any]:
        """Execute a bash command in the remote Vercel Sandbox environment."""
        start_time = time.perf_counter()
        exit_code = -1
        stdout = ""
        stderr = ""

        try:
            await self._sync_workspace()
            if not self.sandbox:
                raise RuntimeError("Vercel Sandbox is not connected.")

            # Run bash command inside the sandbox wrapped via bash -c
            cmd = await self.sandbox.run_command_detached("bash", ["-c", command])
            try:
                cmd_finished = await asyncio.wait_for(cmd.wait(), timeout=timeout)
                exit_code = cmd_finished.exit_code
                stdout = await cmd_finished.stdout()
                stderr = await cmd_finished.stderr()
            except TimeoutError:
                await cmd.kill()
                stdout = ""
                stderr = "Timeout Error: Exceeded limits."
                exit_code = -9
        except Exception as e:
            stdout = ""
            stderr = f"Execution error: {e}"
            exit_code = -1

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
        """Execute Python code in the remote Vercel Sandbox environment."""
        start_time = time.perf_counter()
        exit_code = -1
        stdout = ""
        stderr = ""

        try:
            await self._sync_workspace()
            if not self.sandbox:
                raise RuntimeError("Vercel Sandbox is not connected.")

            # To execute arbitrary code block, write it to a unique temp file on the sandbox
            temp_script_name = f"_amberclaw_{uuid.uuid4().hex}.py"
            await self.sandbox.write_files([
                {
                    "path": temp_script_name,
                    "content": code.encode("utf-8"),
                }
            ])

            # Run Python script
            cmd = await self.sandbox.run_command_detached(
                "python3", [temp_script_name], env=env
            )
            try:
                cmd_finished = await asyncio.wait_for(cmd.wait(), timeout=timeout)
                exit_code = cmd_finished.exit_code
                stdout = await cmd_finished.stdout()
                stderr = await cmd_finished.stderr()
            except TimeoutError:
                await cmd.kill()
                stdout = ""
                stderr = "Timeout Error: Exceeded limits."
                exit_code = -9
        except Exception as e:
            stdout = ""
            stderr = f"Execution error: {e}"
            exit_code = -1

        execution_time_ms = (time.perf_counter() - start_time) * 1000

        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "execution_time_ms": execution_time_ms,
        }
