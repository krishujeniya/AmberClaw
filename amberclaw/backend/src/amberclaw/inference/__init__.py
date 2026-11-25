"""AmberClaw inference orchestration, provider credentials, health monitoring, and profiles."""

from pydantic import BaseModel, Field

from amberclaw.inference.credentials import (
    InferenceCredentialManager,
    ProviderCredential,
)
from amberclaw.inference.health import (
    InferenceHealthMonitor,
    ProviderHealthCheck,
    ProviderHealthStatus,
)
from amberclaw.inference.pii_scanner import (
    InferencePIIScanner,
    PIIMatch,
    PIIScanResult,
)
from amberclaw.inference.profiles import (
    InferenceProfile,
    InferenceTier,
    ProfileRegistry,
)
from amberclaw.inference.proxy import (
    InferenceProxyConfig,
    InferenceProxyManager,
)
from amberclaw.inference.router import (
    InferenceRequest,
    InferenceResponse,
    InferenceRouter,
)


class InferenceModuleConfig(BaseModel):
    """Configuration for the amberclaw.inference module."""

    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")
    default_profile: str = Field(default="balanced")


__all__ = [
    "InferenceCredentialManager",
    "InferenceHealthMonitor",
    "InferenceModuleConfig",
    "InferencePIIScanner",
    "InferenceProfile",
    "InferenceProxyConfig",
    "InferenceProxyManager",
    "InferenceRequest",
    "InferenceResponse",
    "InferenceRouter",
    "InferenceTier",
    "PIIMatch",
    "PIIScanResult",
    "ProfileRegistry",
    "ProviderCredential",
    "ProviderHealthCheck",
    "ProviderHealthStatus",
]
