# ruff: noqa: PLC0415
import asyncio
import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Any

import modal

from amberclaw.terminal.base import BaseTerminalBackend

logger = logging.getLogger(__name__)

# Define Modal App and resources
app = modal.App("amberclaw-sandbox")
nfs = modal.NetworkFileSystem.from_name("amberclaw-workspace", create_if_missing=True)
image = modal.Image.debian_slim().pip_install("python-multipart")


@app.function(
    image=image,
    network_file_systems={"/workspace": nfs},
)
def run_bash(command: str, cwd: str = "/workspace") -> dict[str, Any]:
    """Execute bash command inside the Modal container."""
    import subprocess
    import time
    start_time = time.perf_counter()
    try:
        res = subprocess.run(  # noqa: S602
            command,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        stdout = res.stdout
        stderr = res.stderr
        exit_code = res.returncode
    except Exception as e:
        stdout = ""
        stderr = f"Execution error: {e}"
        exit_code = -1

    return {
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "execution_time_ms": (time.perf_counter() - start_time) * 1000,
    }


@app.function(
    image=image,
    network_file_systems={"/workspace": nfs},
)
def run_python(code: str, env: dict[str, str] | None = None, cwd: str = "/workspace") -> dict[str, Any]:
    """Execute python script inside the Modal container."""
    import io
    import os
    import sys
    import time

    if env:
        os.environ.update(env)

    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    sys.stdout = stdout_buffer
    sys.stderr = stderr_buffer

    start_time = time.perf_counter()
    exit_code = 0
    try:
        os.chdir(cwd)
        exec_globals = {"__name__": "__main__"}
        exec(code, exec_globals)  # noqa: S102
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else 0
    except Exception:
        import traceback
        traceback.print_exc(file=stderr_buffer)
        exit_code = 1
    finally:
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    return {
        "stdout": stdout_buffer.getvalue(),
        "stderr": stderr_buffer.getvalue(),
        "exit_code": exit_code,
        "execution_time_ms": (time.perf_counter() - start_time) * 1000,
    }


class ModalTerminalBackend(BaseTerminalBackend):
    """Terminal execution backend running in Modal cloud container sandboxes."""

    def __init__(self, workspace_dir: str, app_name: str = "amberclaw-sandbox"):
        self.workspace_dir = str(Path(workspace_dir).resolve())
        self.app_name = app_name
        self._connected = False
        self._synced_files: dict[str, str] = {}

    async def connect(self) -> None:
        """Ensure the Modal app is deployed and functions are available."""
        if self._connected:
            return

        try:
            # Test if we can look up the deployed functions
            await asyncio.to_thread(lambda: modal.Function.from_name(self.app_name, "run_bash"))
            self._connected = True
        except Exception:
            # Deploy the app if lookup fails
            logger.info("Modal app '%s' not found. Deploying now...", self.app_name)
            await asyncio.to_thread(lambda: app.deploy(name=self.app_name))
            self._connected = True

    def _get_file_hash(self, path: Path) -> str:
        """Get SHA256 hash of a local file."""
        hasher = hashlib.sha256()
        with path.open("rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _sync_workspace_sync(self, volume: Any) -> None:
        """Synchronously check and upload modified files to Modal NetworkFileSystem."""
        workspace_path = Path(self.workspace_dir)
        if not workspace_path.exists():
            return

        for root, _, files in os.walk(self.workspace_dir):
            for file in files:
                local_file_path = Path(root) / file
                rel_path = local_file_path.relative_to(workspace_path)
                remote_file_path = f"/{rel_path}"

                try:
                    file_hash = self._get_file_hash(local_file_path)
                    if self._synced_files.get(str(rel_path)) != file_hash:
                        with local_file_path.open("rb") as f:
                            volume.write_file(remote_file_path, f)
                        self._synced_files[str(rel_path)] = file_hash
                except Exception as e:
                    logger.warning("Failed to sync file %s to Modal: %s", rel_path, e)

    async def _sync_workspace(self) -> None:
        """Synchronize modified local workspace files to remote NetworkFileSystem."""
        await self.connect()

        volume = await asyncio.to_thread(
            lambda: modal.NetworkFileSystem.from_name("amberclaw-workspace")
        )
        await asyncio.to_thread(self._sync_workspace_sync, volume)

    async def execute_bash(
        self, command: str, timeout: int = 30
    ) -> dict[str, Any]:
        """Execute a bash command in the remote Modal sandbox container."""
        start_time = time.perf_counter()
        await self._sync_workspace()

        try:
            run_bash_fn = await asyncio.to_thread(
                lambda: modal.Function.from_name(self.app_name, "run_bash")
            )

            res = await asyncio.wait_for(
                asyncio.to_thread(lambda: run_bash_fn.remote(command)),
                timeout=timeout,
            )

            exit_code = res.get("exit_code", -1)
            stdout = res.get("stdout", "")
            stderr = res.get("stderr", "")
            execution_time_ms = res.get("execution_time_ms", 0.0)
        except TimeoutError:
            stdout = ""
            stderr = "Timeout Error: Exceeded limits."
            exit_code = -9
            execution_time_ms = (time.perf_counter() - start_time) * 1000
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
        """Execute Python code in the remote Modal sandbox container."""
        start_time = time.perf_counter()
        await self._sync_workspace()

        try:
            run_python_fn = await asyncio.to_thread(
                lambda: modal.Function.from_name(self.app_name, "run_python")
            )

            res = await asyncio.wait_for(
                asyncio.to_thread(lambda: run_python_fn.remote(code, env)),
                timeout=timeout,
            )

            exit_code = res.get("exit_code", -1)
            stdout = res.get("stdout", "")
            stderr = res.get("stderr", "")
            execution_time_ms = res.get("execution_time_ms", 0.0)
        except TimeoutError:
            stdout = ""
            stderr = "Timeout Error: Exceeded limits."
            exit_code = -9
            execution_time_ms = (time.perf_counter() - start_time) * 1000
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
