"""AmberClaw security module."""

from pydantic import BaseModel, Field

from amberclaw.security.abac import (
    ABACAccessDeniedError,
    ABACPolicyEngine,
    ABACPolicyRule,
    JITElevationToken,
    JustInTimeElevationManager,
    PolicyEffect,
    ResourceBoundary,
    SubjectAttributes,
)
from amberclaw.security.approval import (
    ApprovalDecision,
    ApprovalStatus,
    RunawayLoopDetected,
    RunawayLoopGuard,
    ToolApprovalManager,
    ToolRiskLevel,
    ToolSafetyPolicy,
)
from amberclaw.security.auth import (
    RBACPermissionDenied,
    active_sender_context,
    check_tool_permission,
)
from amberclaw.security.dlp import (
    DataLossPreventionEngine,
    DLPAction,
    DLPScanResult,
    DLPSensitivity,
    DLPViolation,
    DLPViolationError,
)
from amberclaw.security.egress_controller import NetworkAccessDenied, egress_sandbox
from amberclaw.security.envelope import (
    EnvelopeEncryptionManager,
    EnvelopePayload,
)
from amberclaw.security.filters import (
    ArgumentValidationError,
    OutputPolicyViolationError,
    ToolCapabilityManifest,
    ToolExecutionFilter,
)
from amberclaw.security.isolation import (
    ProcessIsolationConfig,
    ResourceLimits,
    apply_resource_limits,
    get_preexec_isolation_fn,
)
from amberclaw.security.network_policy import NetworkPolicy
from amberclaw.security.prompt_guard import (
    InjectionScanResult,
    PromptInjectionDetector,
    TrustLevel,
    TrustProvenance,
    UntrustedContentFormatter,
)
from amberclaw.security.secret_scanner import SecretScanner
from amberclaw.security.siem import (
    AuditRetentionManager,
    SIEMExporter,
    SIEMFormat,
)
from amberclaw.security.tokens import (
    APIKeyManager,
    APIKeyRecord,
    BreakGlassElevation,
    BreakGlassManager,
    RefreshTokenManager,
    SecurityCompromiseError,
    TokenPair,
    TokenRevocationStore,
)
from amberclaw.security.vault import SecretVault, resolved_secrets_context, vault


class SecurityModuleConfig(BaseModel):
    """Configuration for the security module."""

    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = [
    "ABACAccessDeniedError",
    "ABACPolicyEngine",
    "ABACPolicyRule",
    "APIKeyManager",
    "APIKeyRecord",
    "ApprovalDecision",
    "ApprovalStatus",
    "ArgumentValidationError",
    "AuditRetentionManager",
    "BreakGlassElevation",
    "BreakGlassManager",
    "DLPAction",
    "DLPScanResult",
    "DLPSensitivity",
    "DLPViolation",
    "DLPViolationError",
    "DataLossPreventionEngine",
    "EnvelopeEncryptionManager",
    "EnvelopePayload",
    "InjectionScanResult",
    "JITElevationToken",
    "JustInTimeElevationManager",
    "NetworkAccessDenied",
    "NetworkPolicy",
    "OutputPolicyViolationError",
    "PolicyEffect",
    "ProcessIsolationConfig",
    "PromptInjectionDetector",
    "RBACPermissionDenied",
    "RefreshTokenManager",
    "ResourceBoundary",
    "ResourceLimits",
    "RunawayLoopDetected",
    "RunawayLoopGuard",
    "SIEMExporter",
    "SIEMFormat",
    "SecretScanner",
    "SecretVault",
    "SecurityCompromiseError",
    "SecurityModuleConfig",
    "SubjectAttributes",
    "TokenPair",
    "TokenRevocationStore",
    "ToolApprovalManager",
    "ToolCapabilityManifest",
    "ToolExecutionFilter",
    "ToolRiskLevel",
    "ToolSafetyPolicy",
    "TrustLevel",
    "TrustProvenance",
    "UntrustedContentFormatter",
    "active_sender_context",
    "apply_resource_limits",
    "check_tool_permission",
    "egress_sandbox",
    "get_preexec_isolation_fn",
    "resolved_secrets_context",
    "vault",
]
