"""Workspace lifecycle manager and directory provisioner."""

import shutil
from pathlib import Path
from typing import Any

from amberclaw.workspaces.runtime import WorkspaceRuntime
from amberclaw.workspaces.workspace import WorkspaceContext


class WorkspaceManager:
    """Manages active workspace instances, filesystem isolation, and lifecycle teardown."""

    def __init__(self, base_storage_dir: Path | str | None = None) -> None:
        self.base_storage_dir = Path(base_storage_dir) if base_storage_dir else Path("./workspaces")
        self._workspaces: dict[str, WorkspaceContext] = {}

    def create_workspace(  # noqa: PLR0913
        self,
        workspace_id: str,
        name: str,
        custom_root: Path | str | None = None,
        is_isolated: bool = True,
        env_vars: dict[str, str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WorkspaceContext:
        """Create or initialize a new managed workspace."""
        if custom_root:
            root_path = Path(custom_root)
        else:
            root_path = self.base_storage_dir / workspace_id

        root_path.mkdir(parents=True, exist_ok=True)

        ctx = WorkspaceContext(
            workspace_id=workspace_id,
            name=name,
            root_path=root_path,
            is_isolated=is_isolated,
            env_vars=env_vars or {},
            metadata=metadata or {},
        )

        self._workspaces[workspace_id] = ctx
        return ctx

    def get_workspace(self, workspace_id: str) -> WorkspaceContext | None:
        """Retrieve an active workspace context by ID."""
        return self._workspaces.get(workspace_id)

    def get_runtime(self, workspace_id: str) -> WorkspaceRuntime | None:
        """Obtain a WorkspaceRuntime instance for an active workspace."""
        ctx = self.get_workspace(workspace_id)
        if not ctx:
            return None
        return WorkspaceRuntime(ctx)

    def list_workspaces(self) -> list[WorkspaceContext]:
        """List all active registered workspaces."""
        return list(self._workspaces.values())

    def delete_workspace(self, workspace_id: str, remove_files: bool = False) -> bool:
        """Unregister a workspace and optionally delete directory from disk."""
        ctx = self._workspaces.pop(workspace_id, None)
        if not ctx:
            return False
        if remove_files and ctx.root_path.exists():
            shutil.rmtree(ctx.root_path, ignore_errors=True)
        return True
