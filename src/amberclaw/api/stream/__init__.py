"""
AmberClaw amberclaw.api.stream module.
"""

from pydantic import BaseModel, Field


class StreamModuleConfig(BaseModel):
    """Configuration for the amberclaw.api.stream module."""
    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = ["StreamModuleConfig"]
