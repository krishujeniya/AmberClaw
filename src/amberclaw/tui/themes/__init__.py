"""
AmberClaw amberclaw.tui.themes module.
"""

from pydantic import BaseModel, Field


class ThemesModuleConfig(BaseModel):
    """Configuration for the amberclaw.tui.themes module."""
    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = ["ThemesModuleConfig"]
