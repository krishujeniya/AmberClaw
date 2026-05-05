"""
AmberClaw amberclaw.security module.
"""

from pydantic import BaseModel, Field


class SecurityModuleConfig(BaseModel):
    """Configuration for the amberclaw.security module."""
    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = ["SecurityModuleConfig"]
