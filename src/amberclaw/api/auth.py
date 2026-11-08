"""API Authentication and Authorization dependencies."""

import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from pydantic import BaseModel, Field

from amberclaw.security.credentials import (
    AuthenticationConfigurationError,
    get_signing_secret,
)
from amberclaw.security.tokens import APIKeyManager, TokenRevocationStore

# Secret key and algorithm for JWT tokens
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# API key for service/automated calls
API_KEY = os.getenv("AMBERCLAW_API_KEY", "")

security_bearer = HTTPBearer(auto_error=False)


class TokenData(BaseModel):
    sub: str | None = None
    role: str = "user"
    scopes: list[str] = Field(default_factory=list)


class UserIdentity(BaseModel):
    user_id: str
    role: str
    scopes: list[str] = Field(default_factory=list)


def create_access_token(
    data: dict[str, Any], expires_delta: timedelta | None = None
) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    try:
        secret = get_signing_secret()
    except AuthenticationConfigurationError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "JWT authentication is not configured"
        ) from exc
    token: object = jwt.encode(to_encode, secret, algorithm=ALGORITHM)
    if not isinstance(token, str):
        raise TypeError("JWT encoder must return a string token")
    return token


async def get_current_user(
    auth: HTTPAuthorizationCredentials | None = Security(security_bearer),
) -> UserIdentity:
    """FastAPI dependency enforcing mandatory API authentication.

    Accepts either Bearer JWT tokens or direct API key in Authorization header.
    """
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth.credentials

    # 1. Check direct API Key (legacy or env)
    if API_KEY and secrets.compare_digest(token.encode(), API_KEY.encode()):
        return UserIdentity(user_id="api_key_user", role="admin", scopes=["*"])

    # 2. Check hashed API Key via APIKeyManager
    if token.startswith("ak_live_"):
        try:
            record = APIKeyManager.get_instance().verify_api_key(token)
            return UserIdentity(
                user_id=record.owner_id,
                role="api_user",
                scopes=record.scopes,
            )
        except PermissionError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"API key verification failed: {e}",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

    # 3. Check JWT Token
    try:
        payload = jwt.decode(
            token,
            get_signing_secret(),
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        if payload.get("type", "access") != "access":
            raise InvalidTokenError("Only access tokens can authorize API requests")
        user_id = payload.get("sub")
        if not isinstance(user_id, str) or not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload: missing sub claim.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check token and session revocation
        jti = payload.get("jti")
        session_id = payload.get("session_id")
        store = TokenRevocationStore.get_instance()
        if jti and store.is_jti_revoked(jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if session_id and store.is_session_revoked(session_id):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        role: str = payload.get("role", "user")
        scopes: list[str] = payload.get("scopes", [])
        return UserIdentity(user_id=user_id, role=role, scopes=scopes)
    except AuthenticationConfigurationError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "JWT authentication is not configured"
        ) from exc
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def require_auth_administrator(
    identity: UserIdentity = Depends(get_current_user),
) -> UserIdentity:
    if identity.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return identity
