"""
AmberClaw amberclaw.security module.
"""

from pydantic import BaseModel, Field

from amberclaw.security.auth import (
    RBACPermissionDenied,
    active_sender_context,
    check_tool_permission,
)
from amberclaw.security.egress_controller import NetworkAccessDenied, egress_sandbox
from amberclaw.security.network_policy import NetworkPolicy
from amberclaw.security.secret_scanner import SecretScanner
from amberclaw.security.vault import SecretVault, resolved_secrets_context, vault


class SecurityModuleConfig(BaseModel):
    """Configuration for the amberclaw.security module."""
    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = [
    "NetworkAccessDenied",
    "NetworkPolicy",
    "RBACPermissionDenied",
    "SecretScanner",
    "SecretVault",
    "SecurityModuleConfig",
    "active_sender_context",
    "check_tool_permission",
    "egress_sandbox",
    "resolved_secrets_context",
    "vault",
]
