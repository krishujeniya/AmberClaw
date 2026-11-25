"""OpenID Connect (OIDC) Enterprise SSO Provider implementation."""

import urllib.parse
from typing import Any

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.jose import JsonWebToken
from authlib.oidc.core import CodeIDToken

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
    """Map already cryptographically verified claims into a user profile.

    This pure mapper is not an authentication boundary. Callbacks must use
    exchange_oidc_code and must never pass browser-supplied claim dictionaries.
    """
    sub = str(claims.get("sub", ""))
    email = str(claims.get("email", sub))
    if not sub and not email:
        raise ValueError("OIDC Claims missing 'sub' and 'email' identity identifiers")

    display_name = str(
        claims.get("name", claims.get("preferred_username", email.split("@", 1)[0]))
    )
    given_name = str(claims.get("given_name", ""))
    family_name = str(claims.get("family_name", ""))

    # Extract roles/groups
    raw_roles = claims.get(config.role_attribute_name, [])
    if isinstance(raw_roles, str):
        raw_roles = [raw_roles]
    elif not isinstance(raw_roles, list):
        raw_roles = []
    else:
        raw_roles = list(raw_roles)

    groups = claims.get("groups", [])
    if isinstance(groups, list):
        raw_roles.extend(str(g) for g in groups)

    mapped_roles: set[str] = set()
    for raw in raw_roles:
        if not isinstance(raw, str):
            continue
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


def _https_endpoint(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("OIDC discovery endpoint is missing")
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.fragment
    ):
        raise ValueError("OIDC endpoints must use HTTPS without user info or fragments")
    return value


async def discover_oidc(config: SSOConfig) -> dict[str, Any]:
    """Retrieve discovery only from the administrator-configured issuer."""
    issuer = _https_endpoint(config.oidc_issuer_url)
    if not config.oidc_client_id:
        raise ValueError("OIDC client ID is required")
    _https_endpoint(config.sp_acs_url)
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        response = await client.get(
            f"{issuer.rstrip('/')}/.well-known/openid-configuration"
        )
        response.raise_for_status()
        metadata = response.json()
    if not isinstance(metadata, dict) or metadata.get("issuer") != issuer:
        raise ValueError("OIDC discovery issuer does not match configuration")
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        _https_endpoint(metadata.get(key))
    return metadata


async def exchange_oidc_code(
    code: str, config: SSOConfig, *, nonce: str, verifier: str, metadata: dict[str, Any]
) -> SSOUserProfile:
    """Exchange a single-use code and verify its signed ID token with issuer keys."""
    async with AsyncOAuth2Client(
        client_id=config.oidc_client_id,
        client_secret=config.oidc_client_secret or None,
        token_endpoint_auth_method="client_secret_basic"
        if config.oidc_client_secret
        else "none",
        timeout=10.0,
        follow_redirects=False,
    ) as client:
        token = await client.fetch_token(
            _https_endpoint(metadata["token_endpoint"]),
            code=code,
            code_verifier=verifier,
            redirect_uri=config.sp_acs_url,
        )
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        response = await client.get(_https_endpoint(metadata["jwks_uri"]))
        response.raise_for_status()
        keys = response.json()
    claims = JsonWebToken(["RS256", "ES256"]).decode(
        token["id_token"],
        key=keys,
        claims_cls=CodeIDToken,
        claims_options={
            "iss": {"essential": True, "value": config.oidc_issuer_url},
            "aud": {"essential": True, "value": config.oidc_client_id},
        },
        claims_params={
            "nonce": nonce,
            "client_id": config.oidc_client_id,
            "access_token": token.get("access_token"),
        },
    )
    claims.validate(leeway=30)
    return validate_oidc_claims(dict(claims), config)
