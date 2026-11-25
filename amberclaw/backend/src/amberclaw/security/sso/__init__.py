"""Enterprise Single Sign-On (SSO) Module supporting SAML 2.0 and OIDC."""

from amberclaw.security.sso.models import SSOConfig, SSOProtocol, SSOUserProfile
from amberclaw.security.sso.oidc import build_oidc_auth_url, validate_oidc_claims
from amberclaw.security.sso.saml import (
    build_authn_request,
    generate_sp_metadata,
    parse_and_verify_saml_response,
)

__all__ = [
    "SSOConfig",
    "SSOProtocol",
    "SSOUserProfile",
    "build_authn_request",
    "build_oidc_auth_url",
    "generate_sp_metadata",
    "parse_and_verify_saml_response",
    "validate_oidc_claims",
]
