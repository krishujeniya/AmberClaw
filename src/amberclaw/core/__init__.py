"""
AmberClaw amberclaw.core module.
"""

from pydantic import BaseModel, Field


from amberclaw.core.kernel import ClawOSSupervisor


class CoreModuleConfig(BaseModel):
    """Configuration for the amberclaw.core module."""
    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = ["CoreModuleConfig", "ClawOSSupervisor"]
