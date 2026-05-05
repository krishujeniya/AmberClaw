"""
AmberClaw amberclaw.skills module.
"""

from pydantic import BaseModel, Field


class SkillsModuleConfig(BaseModel):
    """Configuration for the amberclaw.skills module."""
    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = ["SkillsModuleConfig"]
