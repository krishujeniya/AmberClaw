"""AmberClaw workspace containment, runtime, Git operations, and lifecycle manager."""

from pydantic import BaseModel, Field

from amberclaw.workspaces.git_ops import GitOps
from amberclaw.workspaces.manager import WorkspaceManager
from amberclaw.workspaces.runtime import ExecutionResult, WorkspaceRuntime
from amberclaw.workspaces.workspace import WorkspaceContext


class WorkspacesModuleConfig(BaseModel):
    """Configuration for the amberclaw.workspaces module."""

    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = [
    "ExecutionResult",
    "GitOps",
    "WorkspaceContext",
    "WorkspaceManager",
    "WorkspaceRuntime",
    "WorkspacesModuleConfig",
]
