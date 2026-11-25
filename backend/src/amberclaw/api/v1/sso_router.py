"""Browser-bound SAML and OIDC login; raw identity claims are never credentials."""

import asyncio
import base64
import hashlib
import json
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from amberclaw.api.auth import create_access_token
from amberclaw.security.sso.models import SSOConfig, SSOProtocol, SSOUserProfile
from amberclaw.security.sso.oidc import discover_oidc, exchange_oidc_code
from amberclaw.security.sso.requests import LOGIN_TTL, SSO_COOKIE, LoginRequests
from amberclaw.security.sso.saml import (
    build_authn_request,
    generate_sp_metadata,
    parse_and_verify_saml_response,
)

router = APIRouter()
_requests = LoginRequests()
MAX_CALLBACK_BYTES = 1_100_000


class _SSOHolder:
    config: SSOConfig = SSOConfig()


def get_sso_config() -> SSOConfig:
    return _SSOHolder.config


def set_sso_config(config: SSOConfig) -> None:
    _requests.clear()
    _SSOHolder.config = config.model_copy(deep=True)


def _enabled_config() -> SSOConfig:
    config = get_sso_config()
    if not config.enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SSO is disabled")
    return config


class SSOCallbackRequest(BaseModel):
    saml_response: str | None = Field(
        default=None, alias="SAMLResponse", max_length=1_000_000
    )
    relay_state: str | None = Field(default=None, alias="RelayState", max_length=256)
    code: str | None = Field(default=None, max_length=8192)
    state: str | None = Field(default=None, max_length=256)
    claims: dict[str, Any] | None = None


class SSOLoginResponse(BaseModel):
    access_token: str
    token_type: str = Field(default="bearer")
    expires_in: int = 3600
    user_profile: SSOUserProfile


@router.get("/metadata", response_class=Response)
async def get_saml_metadata() -> Response:
    xml = await asyncio.to_thread(generate_sp_metadata, _enabled_config())
    return Response(content=xml, media_type="application/xml")


@router.get("/login")
async def initiate_sso_login() -> RedirectResponse:
    config = _enabled_config()
    state, login = _requests.create(config)
    try:
        if config.protocol == SSOProtocol.SAML2:
            data = await asyncio.to_thread(
                build_authn_request, config, relay_state=state
            )
            login.request_id = data["request_id"]
            url = data["redirect_url"]
        else:
            login.metadata = await discover_oidc(config)
            challenge = (
                base64.urlsafe_b64encode(
                    hashlib.sha256(login.verifier.encode()).digest()
                )
                .rstrip(b"=")
                .decode()
            )
            params = {
                "client_id": config.oidc_client_id,
                "redirect_uri": config.sp_acs_url,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "nonce": login.nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
            url = f"{login.metadata['authorization_endpoint']}?{urlencode(params)}"
    except Exception as exc:
        _requests.consume(state, state)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "SSO provider is unavailable or misconfigured",
        ) from exc
    response = RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        SSO_COOKIE,
        state,
        max_age=LOGIN_TTL,
        secure=True,
        httponly=True,
        samesite="none",
        path="/api/v1/auth/sso",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


async def _callback_payload(request: Request) -> SSOCallbackRequest:
    if request.method == "GET":
        return SSOCallbackRequest(
            code=request.query_params.get("code"),
            state=request.query_params.get("state"),
        )
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_CALLBACK_BYTES:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "SSO response too large"
            )
    content_type = request.headers.get("content-type", "").split(";")[0]
    try:
        if content_type == "application/json":
            data = json.loads(body)
        elif content_type == "application/x-www-form-urlencoded":
            fields = parse_qs(body.decode(), max_num_fields=16)
            if any(len(values) != 1 for values in fields.values()):
                raise ValueError("Repeated SSO callback fields")
            data = {key: values[0] for key, values in fields.items()}
        else:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                "Unsupported SSO callback content type",
            )
        return SSOCallbackRequest.model_validate(data)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Malformed SSO callback"
        ) from exc


@router.get("/callback", response_model=SSOLoginResponse)
@router.post("/callback", response_model=SSOLoginResponse)
async def handle_sso_callback(request: Request, response: Response) -> SSOLoginResponse:
    _enabled_config()
    payload = await _callback_payload(request)
    if payload.claims is not None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Unverified identity claims are not accepted"
        )
    if not payload.saml_response and not payload.code:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Missing SAMLResponse or authorization code"
        )
    try:
        login = _requests.consume(
            payload.relay_state or payload.state or "",
            request.cookies.get(SSO_COOKIE, ""),
        )
        configured = urlsplit(login.config.sp_acs_url)
        actual = urlsplit(str(request.url))
        if (actual.scheme, actual.netloc, actual.path) != (
            configured.scheme,
            configured.netloc,
            configured.path,
        ):
            raise ValueError("SSO callback URL does not match configured ACS")
        if login.config.protocol == SSOProtocol.SAML2 and payload.saml_response:
            profile = await asyncio.to_thread(
                parse_and_verify_saml_response,
                payload.saml_response,
                login.config,
                request_id=login.request_id,
            )
        elif login.config.protocol == SSOProtocol.OIDC and payload.code:
            profile = await exchange_oidc_code(
                payload.code,
                login.config,
                nonce=login.nonce,
                verifier=login.verifier,
                metadata=login.metadata,
            )
        else:
            raise ValueError("SSO callback protocol mismatch")
    except Exception as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "SSO verification failed"
        ) from exc
    response.delete_cookie(SSO_COOKIE, path="/api/v1/auth/sso")
    response.headers["Cache-Control"] = "no-store"
    token = create_access_token(
        data={
            "email": profile.email,
            "role": profile.roles[0] if profile.roles else "user",
            "roles": profile.roles,
            "sso": True,
            "sub": profile.user_id,
        }
    )
    return SSOLoginResponse(access_token=token, user_profile=profile)
