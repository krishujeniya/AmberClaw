"""
AmberClaw amberclaw.inference module.
"""

from pydantic import BaseModel, Field


class InferenceModuleConfig(BaseModel):
    """Configuration for the amberclaw.inference module."""
    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = ["InferenceModuleConfig"]
