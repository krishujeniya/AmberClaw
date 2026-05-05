"""
AmberClaw amberclaw.blueprints module.
"""

from pydantic import BaseModel, Field


class BlueprintsModuleConfig(BaseModel):
    """Configuration for the amberclaw.blueprints module."""
    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = ["BlueprintsModuleConfig"]
