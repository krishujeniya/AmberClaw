"""
AmberClaw amberclaw.api.v1 module.
"""

from pydantic import BaseModel, Field


class V1ModuleConfig(BaseModel):
    """Configuration for the amberclaw.api.v1 module."""
    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = ["V1ModuleConfig"]
