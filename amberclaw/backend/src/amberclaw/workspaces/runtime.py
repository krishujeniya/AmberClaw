"""Execution runtime enforcing workspace boundaries and safe file I/O."""

import os
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from amberclaw.workspaces.workspace import WorkspaceContext


class ExecutionResult(BaseModel):
    """Result of command execution within workspace."""

    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float = Field(default=0.0)


class WorkspaceRuntime:
    """Provides sandboxed file operations and command execution in workspace."""

    def __init__(self, context: WorkspaceContext) -> None:
        self.context = context

    def read_file(self, relative_path: str | Path) -> str:
        """Safely read content from a file within workspace boundary."""
        target = self.context.resolve_path(relative_path)
        if not target.is_file():
            raise FileNotFoundError(f"File not found: {relative_path}")
        return target.read_text(encoding="utf-8")

    def write_file(self, relative_path: str | Path, content: str) -> Path:
        """Safely write content to a file within workspace boundary, creating parent directories."""
        target = self.context.resolve_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def list_files(self, sub_dir: str | Path = "") -> list[str]:
        """List files relative to workspace root."""
        target_dir = self.context.resolve_path(sub_dir)
        if not target_dir.is_dir():
            return []
        root = self.context.root_path.resolve()
        return [str(p.relative_to(root)) for p in target_dir.rglob("*") if p.is_file()]

    def run_command(
        self,
        command: list[str],
        timeout_seconds: float = 30.0,
        extra_env: dict[str, str] | None = None,
    ) -> ExecutionResult:
        """Execute a command strictly anchored to the workspace root directory."""
        env = os.environ.copy()
        env.update(self.context.env_vars)
        if extra_env:
            env.update(extra_env)

        try:
            res = subprocess.run(  # noqa: S603
                command,
                cwd=self.context.root_path,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            return ExecutionResult(
                command=" ".join(command),
                exit_code=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr,
            )
        except subprocess.TimeoutExpired as e:
            return ExecutionResult(
                command=" ".join(command),
                exit_code=124,
                stdout="",
                stderr=f"Command timed out after {timeout_seconds}s: {e}",
            )
        except Exception as e:
            return ExecutionResult(
                command=" ".join(command),
                exit_code=1,
                stdout="",
                stderr=f"Execution error: {e}",
            )
