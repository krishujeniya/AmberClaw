"""
AmberClaw amberclaw.governance module.
"""

from pydantic import BaseModel, Field


class GovernanceModuleConfig(BaseModel):
    """Configuration for the amberclaw.governance module."""
    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = ["GovernanceModuleConfig"]
