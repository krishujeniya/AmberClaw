"""Workspace context data structures and filesystem containment."""

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class WorkspaceContext(BaseModel):
    """Encapsulates the state, configuration, and filesystem boundaries of a workspace."""

    workspace_id: str = Field(..., description="Unique workspace identifier.")
    name: str = Field(..., description="Workspace human-readable name.")
    root_path: Path = Field(..., description="Absolute root directory on host filesystem.")
    is_isolated: bool = Field(default=True, description="Whether strict filesystem isolation is enforced.")
    env_vars: dict[str, str] = Field(default_factory=dict, description="Environment variables injected into commands.")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def resolve_path(self, relative_path: str | Path) -> Path:
        """Resolve a relative path inside the workspace root, preventing directory traversal escaping."""
        target = (self.root_path / relative_path).resolve()
        root_resolved = self.root_path.resolve()

        if self.is_isolated:
            try:
                target.relative_to(root_resolved)
            except ValueError as err:
                raise PermissionError(
                    f"Access denied: path '{relative_path}' escapes workspace boundary '{root_resolved}'."
                ) from err

        return target

    def ensure_directory(self, sub_dir: str | Path = "") -> Path:
        """Ensure a workspace subdirectory exists and return its resolved path."""
        p = self.resolve_path(sub_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p
