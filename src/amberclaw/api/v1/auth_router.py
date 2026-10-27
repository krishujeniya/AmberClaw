# ruff: noqa: S105
"""API authentication endpoints with JWT, Rotating Refresh Tokens, API Key Lifecycle, and Break-Glass."""

import os
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from amberclaw.security.tokens import (
    APIKeyManager,
    BreakGlassManager,
    RefreshTokenManager,
    SecurityCompromiseError,
    TokenPair,
    TokenRevocationStore,
)

router = APIRouter()


class TokenRequest(BaseModel):
    client_id: str
    client_secret: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int = 3600


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RevokeTokenRequest(BaseModel):
    jti: str | None = None
    session_id: str | None = None


class CreateAPIKeyRequest(BaseModel):
    owner_id: str
    scopes: list[str] = Field(default_factory=lambda: ["*"])
    name: str = "API Key"
    expires_in_days: int | None = 30


class APIKeyResponse(BaseModel):
    key_id: str
    key_prefix: str
    raw_key: str
    owner_id: str
    scopes: list[str]
    expires_at: str | None


class RotateAPIKeyRequest(BaseModel):
    key_id: str
    expires_in_days: int | None = 30


class BreakGlassRequest(BaseModel):
    user_id: str
    reason: str
    duration_minutes: int = 60


class BreakGlassResponse(BaseModel):
    elevation_id: str
    user_id: str
    reason: str
    expires_at: str
    is_active: bool


@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(request: TokenRequest) -> TokenResponse:
    """Issue JWT access and rotating refresh token for client authentication."""
    expected_id = os.getenv("AUTH_CLIENT_ID", "admin")
    expected_secret = os.getenv("AUTH_CLIENT_SECRET", "amberclaw-secret")

    if request.client_id != expected_id or request.client_secret != expected_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    mgr = RefreshTokenManager()
    pair = mgr.create_token_pair(
        user_id=request.client_id,
        role="admin",
        scopes=["*"],
    )

    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        token_type=pair.token_type,
        expires_in=pair.expires_in,
    )


@router.post("/token/refresh", response_model=TokenPair)
async def refresh_access_token(request: RefreshTokenRequest) -> TokenPair:
    """Rotate an existing refresh token and obtain a fresh access token."""
    mgr = RefreshTokenManager()
    try:
        return mgr.rotate_refresh_token(request.refresh_token)
    except SecurityCompromiseError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Security alert: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unauthorized: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


@router.post("/token/revoke", status_code=status.HTTP_200_OK)
async def revoke_token_or_session(request: RevokeTokenRequest) -> dict[str, Any]:
    """Revoke a specific token JTI or all tokens for an entire session."""
    store = TokenRevocationStore.get_instance()
    if request.jti:
        store.revoke_jti(request.jti)
    if request.session_id:
        store.revoke_session(request.session_id)
    return {"status": "revoked", "jti": request.jti, "session_id": request.session_id}


@router.post(
    "/api-keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED
)
async def create_api_key(request: CreateAPIKeyRequest) -> APIKeyResponse:
    """Generate a hashed API key with assigned scopes and expiration."""
    mgr = APIKeyManager.get_instance()
    record, raw_key = mgr.create_api_key(
        owner_id=request.owner_id,
        scopes=request.scopes,
        name=request.name,
        expires_in_days=request.expires_in_days,
    )
    return APIKeyResponse(
        key_id=record.key_id,
        key_prefix=record.key_prefix,
        raw_key=raw_key,
        owner_id=record.owner_id,
        scopes=record.scopes,
        expires_at=record.expires_at.isoformat() if record.expires_at else None,
    )


@router.post("/api-keys/rotate", response_model=APIKeyResponse)
async def rotate_api_key(request: RotateAPIKeyRequest) -> APIKeyResponse:
    """Rotate an existing API key, invalidating the previous key."""
    mgr = APIKeyManager.get_instance()
    try:
        record, raw_key = mgr.rotate_api_key(
            key_id=request.key_id,
            new_expires_in_days=request.expires_in_days,
        )
        return APIKeyResponse(
            key_id=record.key_id,
            key_prefix=record.key_prefix,
            raw_key=raw_key,
            owner_id=record.owner_id,
            scopes=record.scopes,
            expires_at=record.expires_at.isoformat() if record.expires_at else None,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post("/auth/break-glass", response_model=BreakGlassResponse)
async def trigger_break_glass(request: BreakGlassRequest) -> BreakGlassResponse:
    """Emergency break-glass elevation requiring strict justification and creating an audit record."""
    mgr = BreakGlassManager.get_instance()
    try:
        elevation = mgr.request_break_glass(
            user_id=request.user_id,
            reason=request.reason,
            duration_minutes=request.duration_minutes,
        )
        return BreakGlassResponse(
            elevation_id=elevation.elevation_id,
            user_id=elevation.user_id,
            reason=elevation.reason,
            expires_at=elevation.expires_at.isoformat(),
            is_active=elevation.is_active,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
