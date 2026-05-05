"""
AmberClaw amberclaw.agent.planning module.
"""

from pydantic import BaseModel, Field


class PlanningModuleConfig(BaseModel):
    """Configuration for the amberclaw.agent.planning module."""
    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = ["PlanningModuleConfig"]
