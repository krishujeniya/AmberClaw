"""
AmberClaw amberclaw.cli.commands module.
"""

from pydantic import BaseModel, Field


class CommandsModuleConfig(BaseModel):
    """Configuration for the amberclaw.cli.commands module."""
    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = ["CommandsModuleConfig"]
