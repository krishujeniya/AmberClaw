"""
AmberClaw amberclaw.agent.learning module.
"""

from pydantic import BaseModel, Field


class LearningModuleConfig(BaseModel):
    """Configuration for the amberclaw.agent.learning module."""
    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = ["LearningModuleConfig"]
