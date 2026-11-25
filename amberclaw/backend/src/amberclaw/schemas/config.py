"""Pydantic schemas for runtime server and provider configuration."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GatewayConfigSchema(BaseModel):
    """Configuration for API Gateway server."""

    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000, ge=1, le=65535)
    workers: int = Field(default=1, ge=1)
    reload: bool = Field(default=False)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:8080"])


class SecurityConfigSchema(BaseModel):
    """Configuration for zero-trust security controls."""

    sandbox_type: str = Field(default="docker")
    audit_enabled: bool = Field(default=True)
    mtls_enabled: bool = Field(default=False)
    require_mfa: bool = Field(default=False)
    rate_limit_per_minute: int = Field(default=60, ge=1)


class ProviderConfigSchema(BaseModel):
    """Configuration schema for individual LLM providers."""

    name: str
    api_key: str | None = None
    base_url: str | None = None
    default_model: str = "gpt-4o"
    timeout_seconds: float = 30.0
    extra_headers: dict[str, str] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)
