"""FastAPI router for SAML 2.0 and OIDC Enterprise Single Sign-On (SSO)."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from amberclaw.api.auth import create_access_token
from amberclaw.security.sso.models import SSOConfig, SSOProtocol, SSOUserProfile
from amberclaw.security.sso.oidc import build_oidc_auth_url, validate_oidc_claims
from amberclaw.security.sso.saml import (
    build_authn_request,
    generate_sp_metadata,
    parse_and_verify_saml_response,
)

router = APIRouter()


class _SSOHolder:
    config: SSOConfig = SSOConfig()


def get_sso_config() -> SSOConfig:
    return _SSOHolder.config


def set_sso_config(config: SSOConfig) -> None:
    _SSOHolder.config = config


class SSOCallbackRequest(BaseModel):
    """Callback payload for SAML or OIDC login."""

    saml_response: str | None = Field(default=None, alias="SAMLResponse")
    relay_state: str | None = Field(default=None, alias="RelayState")
    code: str | None = None
    state: str | None = None
    claims: dict[str, Any] | None = None


class SSOLoginResponse(BaseModel):
    """Response returned upon successful SSO assertion exchange."""

    access_token: str
    token_type: str = Field(default="bearer")
    expires_in: int = 3600
    user_profile: SSOUserProfile


@router.get("/metadata", response_class=Response)
async def get_saml_metadata() -> Response:
    """Export SAML 2.0 Service Provider Metadata XML."""
    config = get_sso_config()
    xml_content = generate_sp_metadata(config)
    return Response(content=xml_content, media_type="application/xml")


@router.get("/login")
async def initiate_sso_login(relay_state: str = "") -> RedirectResponse:
    """Initiate SSO login by redirecting to Identity Provider."""
    config = get_sso_config()
    if config.protocol == SSOProtocol.SAML2:
        authn_data = build_authn_request(config, relay_state=relay_state)
        return RedirectResponse(url=authn_data["redirect_url"], status_code=status.HTTP_302_FOUND)

    # OIDC
    oidc_url = build_oidc_auth_url(config, state=relay_state or "amberclaw_sso", nonce="nonce_123")
    return RedirectResponse(url=oidc_url, status_code=status.HTTP_302_FOUND)


@router.post("/callback", response_model=SSOLoginResponse)
async def handle_sso_callback(request: Request, body: SSOCallbackRequest | None = None) -> SSOLoginResponse:
    """Process SAML Assertion or OIDC tokens from IdP and issue JWT."""
    config = get_sso_config()
    saml_b64: str | None = None
    oidc_claims: dict[str, Any] | None = None

    # Check JSON body or Form data
    if body and body.saml_response:
        saml_b64 = body.saml_response
    elif body and body.claims:
        oidc_claims = body.claims
    else:
        # Check Form / Query
        form_data = await request.form()
        saml_b64 = form_data.get("SAMLResponse") or form_data.get("saml_response")  # type: ignore[assignment]

    user_profile: SSOUserProfile | None = None

    if saml_b64:
        try:
            user_profile = parse_and_verify_saml_response(saml_b64, config)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"SAML assertion verification failed: {e}",
            ) from e
    elif oidc_claims:
        try:
            user_profile = validate_oidc_claims(oidc_claims, config)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"OIDC validation failed: {e}",
            ) from e
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing SAMLResponse or OIDC claims in callback payload",
        )

    # Issue AmberClaw access token
    primary_role = user_profile.roles[0] if user_profile.roles else "user"
    token = create_access_token(
        data={
            "email": user_profile.email,
            "role": primary_role,
            "roles": user_profile.roles,
            "sso": True,
            "sub": user_profile.user_id,
        }
    )

    return SSOLoginResponse(access_token=token, user_profile=user_profile)
