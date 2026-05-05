"""
AmberClaw amberclaw.tui module.
"""

from pydantic import BaseModel, Field


class TuiModuleConfig(BaseModel):
    """Configuration for the amberclaw.tui module."""
    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = ["TuiModuleConfig"]
