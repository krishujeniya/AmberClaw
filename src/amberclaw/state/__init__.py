"""
AmberClaw amberclaw.state module.
"""

from pydantic import BaseModel, Field


class StateModuleConfig(BaseModel):
    """Configuration for the amberclaw.state module."""
    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = ["StateModuleConfig"]
