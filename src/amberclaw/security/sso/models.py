"""Data models and schemas for SAML 2.0 and OIDC Enterprise Single Sign-On (SSO)."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SSOProtocol(StrEnum):
    """Supported Enterprise SSO protocols."""

    SAML2 = "saml2"
    OIDC = "oidc"


class SSOUserProfile(BaseModel):
    """Normalized user identity profile extracted from SAML or OIDC assertions."""

    user_id: str
    email: str
    display_name: str = ""
    first_name: str = ""
    last_name: str = ""
    roles: list[str] = Field(default_factory=lambda: ["user"])
    groups: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    authenticated_at_utc: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class SSOConfig(BaseModel):
    """Enterprise SSO Configuration for SAML 2.0 and OIDC."""

    protocol: SSOProtocol = Field(default=SSOProtocol.SAML2)
    enabled: bool = True
    sp_entity_id: str = Field(default="https://amberclaw.ai/auth/sso/saml/metadata")
    sp_acs_url: str = Field(default="https://amberclaw.ai/api/v1/auth/sso/callback")
    idp_entity_id: str = Field(default="https://idp.enterprise.com/saml/metadata")
    idp_sso_url: str = Field(default="https://idp.enterprise.com/saml/sso")
    idp_x509_cert: str = Field(default="", description="PEM certificate of the Identity Provider for signature verification")
    oidc_issuer_url: str = Field(default="https://accounts.google.com")
    oidc_client_id: str = Field(default="")
    oidc_client_secret: str = Field(default="")
    role_attribute_name: str = Field(default="roles", description="SAML/OIDC attribute containing assigned roles")
    default_role: str = "user"
    role_mapping: dict[str, str] = Field(
        default_factory=lambda: {
            "AmberClaw-Admins": "admin",
            "AmberClaw-Operators": "operator",
            "AmberClaw-Auditors": "auditor",
            "AmberClaw-Users": "user",
        }
    )
