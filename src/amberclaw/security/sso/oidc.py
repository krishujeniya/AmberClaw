"""OpenID Connect (OIDC) Enterprise SSO Provider implementation."""

import urllib.parse
from typing import Any

from amberclaw.security.sso.models import SSOConfig, SSOUserProfile


def build_oidc_auth_url(config: SSOConfig, state: str, nonce: str) -> str:
    """Construct OIDC Authorization Code redirect URL."""
    auth_endpoint = f"{config.oidc_issuer_url.rstrip('/')}/protocol/openid-connect/auth"
    params = {
        "client_id": config.oidc_client_id,
        "nonce": nonce,
        "redirect_uri": config.sp_acs_url,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
    }
    return f"{auth_endpoint}?{urllib.parse.urlencode(params)}"


def validate_oidc_claims(claims: dict[str, Any], config: SSOConfig) -> SSOUserProfile:
    """Validate OIDC token claims and map to normalized AmberClaw SSOUserProfile."""
    sub = str(claims.get("sub", ""))
    email = str(claims.get("email", sub))
    if not sub and not email:
        raise ValueError("OIDC Claims missing 'sub' and 'email' identity identifiers")

    display_name = str(claims.get("name", claims.get("preferred_username", email.split("@", 1)[0])))
    given_name = str(claims.get("given_name", ""))
    family_name = str(claims.get("family_name", ""))

    # Extract roles/groups
    raw_roles = claims.get(config.role_attribute_name, [])
    if isinstance(raw_roles, str):
        raw_roles = [raw_roles]
    elif not isinstance(raw_roles, list):
        raw_roles = []

    groups = claims.get("groups", [])
    if isinstance(groups, list):
        raw_roles.extend(str(g) for g in groups)

    mapped_roles: set[str] = set()
    for raw in raw_roles:
        if raw in config.role_mapping:
            mapped_roles.add(config.role_mapping[raw])
        elif raw.lower() in ("admin", "operator", "auditor", "user"):
            mapped_roles.add(raw.lower())

    if not mapped_roles:
        mapped_roles.add(config.default_role)

    return SSOUserProfile(
        attributes=claims,
        display_name=display_name,
        email=email,
        first_name=given_name,
        groups=[str(r) for r in raw_roles],
        last_name=family_name,
        roles=sorted(mapped_roles),
        user_id=sub or email,
    )
