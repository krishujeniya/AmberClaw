"""AmberClaw persistent state management, checkpoints, and versioned schema migrations."""

from pydantic import BaseModel, Field

from amberclaw.state.manager import CheckpointMetadata, StateManager
from amberclaw.state.migration import MigrationStep, StateMigrator


class StateModuleConfig(BaseModel):
    """Configuration for the amberclaw.state module."""

    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = [
    "CheckpointMetadata",
    "MigrationStep",
    "StateManager",
    "StateMigrator",
    "StateModuleConfig",
]
