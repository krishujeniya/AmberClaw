"""
AmberClaw amberclaw.security module.
"""

from pydantic import BaseModel, Field

from amberclaw.security.egress_controller import NetworkAccessDenied, egress_sandbox
from amberclaw.security.network_policy import NetworkPolicy


class SecurityModuleConfig(BaseModel):
    """Configuration for the amberclaw.security module."""
    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = ["SecurityModuleConfig", "egress_sandbox", "NetworkAccessDenied", "NetworkPolicy"]
