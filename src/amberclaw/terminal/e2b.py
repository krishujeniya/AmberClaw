import asyncio
import contextlib
import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Any

from e2b import AsyncSandbox, CommandExitException, SandboxException, TimeoutException
from e2b.sandbox.filesystem.filesystem import WriteEntry

from amberclaw.terminal.base import BaseTerminalBackend

logger = logging.getLogger(__name__)


class E2BTerminalBackend(BaseTerminalBackend):
    """Terminal execution backend running in E2B Firecracker MicroVM sandboxes."""

    def __init__(
        self,
        workspace_dir: str,
        api_key: str | None = None,
        template: str | None = None,
    ):
        self.workspace_dir = str(Path(workspace_dir).resolve())
        self.api_key = api_key or os.getenv("E2B_API_KEY")
        self.template = template
        self.sandbox: AsyncSandbox | None = None
        self._synced_files: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Ensure the E2B sandbox is initialized and running."""
        if self.sandbox is not None:
            return

        logger.info("Initializing E2B sandbox...")
        try:
            # Create the sandbox. If template is provided, use it; otherwise default template.
            kwargs: dict[str, Any] = {}
            if self.api_key:
                kwargs["api_key"] = self.api_key
            if self.template:
                kwargs["template"] = self.template

            self.sandbox = await AsyncSandbox.create(**kwargs)
            logger.info(
                "E2B sandbox initialized successfully with ID: %s",
                self.sandbox.sandbox_id,
            )
        except Exception as e:
            logger.error("Failed to initialize E2B sandbox: %s", e)
            self.sandbox = None
            raise

    async def close(self) -> None:
        """Close and kill the E2B sandbox."""
        async with self._lock:
            if self.sandbox is not None:
                logger.info("Closing E2B sandbox: %s", self.sandbox.sandbox_id)
                try:
                    await self.sandbox.kill()
                except Exception as e:
                    logger.warning("Error killing E2B sandbox: %s", e)
                finally:
                    self.sandbox = None
                    self._synced_files.clear()

    def _get_file_hash(self, path: Path) -> str:
        """Get SHA256 hash of a local file."""
        hasher = hashlib.sha256()
        with path.open("rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _prepare_sync_payload(self) -> tuple[list[WriteEntry], dict[str, str]]:
        """Walk workspace, calculate hashes, read modified files synchronously."""
        files_to_upload: list[WriteEntry] = []
        new_synced_files = dict(self._synced_files)

        workspace_path = Path(self.workspace_dir)
        if not workspace_path.exists():
            return files_to_upload, new_synced_files

        for root, _, files in os.walk(self.workspace_dir):
            for file in files:
                local_file_path = Path(root) / file
                rel_path = local_file_path.relative_to(workspace_path)
                rel_path_str = str(rel_path)

                try:
                    file_hash = self._get_file_hash(local_file_path)
                    if self._synced_files.get(rel_path_str) != file_hash:
                        with local_file_path.open("rb") as f:
                            content = f.read()

                        # In E2B, default directory is /home/user
                        # We upload files to /home/user/rel_path_str
                        files_to_upload.append(
                            {
                                "path": f"/home/user/{rel_path_str}",
                                "data": content,
                            }
                        )
                        new_synced_files[rel_path_str] = file_hash
                except Exception as e:
                    logger.warning(
                        "Failed to prepare file %s for sync: %s", rel_path_str, e
                    )

        return files_to_upload, new_synced_files

    async def _sync_workspace(self) -> None:
        """Synchronize modified local workspace files to the remote sandbox environment."""
        await self.connect()
        if not self.sandbox:
            raise RuntimeError("E2B Sandbox is not connected.")

        # Prepare payload off the main thread to avoid blocking event loop
        files_to_upload, new_synced_files = await asyncio.to_thread(
            self._prepare_sync_payload
        )

        if files_to_upload:
            try:
                # E2B write_files accepts a list of WriteEntry dictionaries
                await self.sandbox.files.write_files(files_to_upload)
                self._synced_files.update(new_synced_files)
                logger.info(
                    "Successfully synced %d files to E2B sandbox.", len(files_to_upload)
                )
            except Exception as e:
                logger.error("Failed to upload synced files to E2B sandbox: %s", e)
                # Clear connection if sandbox is dead
                if isinstance(e, SandboxException):
                    self.sandbox = None
                raise

    async def execute_bash(self, command: str, timeout: int = 30) -> dict[str, Any]:
        """Execute a bash command in the remote E2B sandbox."""
        start_time = time.perf_counter()
        async with self._lock:
            try:
                await self._sync_workspace()
                if not self.sandbox:
                    raise RuntimeError("E2B Sandbox is not connected.")

                res = await self.sandbox.commands.run(command, timeout=timeout)
                stdout = res.stdout
                stderr = res.stderr
                exit_code = res.exit_code
            except CommandExitException as e:
                stdout = e.stdout
                stderr = e.stderr
                exit_code = e.exit_code
            except TimeoutException:
                stdout = ""
                stderr = "Timeout Error: Exceeded limits."
                exit_code = -9
            except Exception as e:
                stdout = ""
                stderr = f"Execution error: {e}"
                exit_code = -1
                # If the sandbox connection failed, clear sandbox reference
                if not self.sandbox or isinstance(e, SandboxException):
                    self.sandbox = None

        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "execution_time_ms": (time.perf_counter() - start_time) * 1000,
        }

    async def execute_python(
        self,
        code: str,
        timeout: int = 30,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute Python code in the remote E2B sandbox."""
        start_time = time.perf_counter()
        async with self._lock:
            try:
                await self._sync_workspace()
                if not self.sandbox:
                    raise RuntimeError("E2B Sandbox is not connected.")

                # Write code to a remote script file in /tmp/
                # We use a hash of the code to avoid conflict on concurrent writes
                code_hash = hashlib.sha256(code.encode()).hexdigest()[:8]
                remote_script_path = f"/tmp/run_{code_hash}.py"  # noqa: S108
                await self.sandbox.files.write(remote_script_path, code)

                # Prepend env to command if provided
                env_prefix = ""
                if env:
                    env_prefix = " ".join(f"{k}={v}" for k, v in env.items()) + " "

                cmd_str = f"{env_prefix}python3 {remote_script_path}"
                res = await self.sandbox.commands.run(cmd_str, timeout=timeout)
                stdout = res.stdout
                stderr = res.stderr
                exit_code = res.exit_code

                # Clean up the script file asynchronously
                with contextlib.suppress(Exception):
                    await self.sandbox.files.remove(remote_script_path)

            except CommandExitException as e:
                stdout = e.stdout
                stderr = e.stderr
                exit_code = e.exit_code
            except TimeoutException:
                stdout = ""
                stderr = "Timeout Error: Exceeded limits."
                exit_code = -9
            except Exception as e:
                stdout = ""
                stderr = f"Execution error: {e}"
                exit_code = -1
                if not self.sandbox or isinstance(e, SandboxException):
                    self.sandbox = None

        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "execution_time_ms": (time.perf_counter() - start_time) * 1000,
        }
