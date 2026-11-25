"""API Authentication and Authorization dependencies."""

import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from pydantic import BaseModel, Field

from amberclaw.security.auth import _current_sender_id
from amberclaw.security.credentials import (
    AuthenticationConfigurationError,
    get_signing_secret,
)
from amberclaw.security.tokens import APIKeyManager, TokenRevocationStore
from amberclaw.storage.tenant import _current_tenant_var

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
    tenant_id: str = "default"
    role: str = "user"
    scopes: list[str] = Field(default_factory=list)


def create_access_token(
    data: dict[str, Any], expires_delta: timedelta | None = None
) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    if "tenant_id" not in to_encode and "org_id" in to_encode:
        to_encode["tenant_id"] = to_encode["org_id"]
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
    request: Request = None,
    auth: HTTPAuthorizationCredentials | None = Security(security_bearer),
) -> UserIdentity:
    """FastAPI dependency enforcing mandatory API authentication.

    Accepts either Bearer JWT tokens or direct API key in Authorization header.
    Strictly scopes execution to authenticated tenant and prevents tenant escalation.
    """
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth.credentials
    user_id: str
    tenant_id: str = "default"
    role: str = "user"
    scopes: list[str] = []

    # 1. Check direct API Key (legacy or env)
    if API_KEY and secrets.compare_digest(token.encode(), API_KEY.encode()):
        user_id = "api_key_user"
        tenant_id = "default"
        role = "admin"
        scopes = ["*"]

    # 2. Check hashed API Key via APIKeyManager
    elif token.startswith("ak_live_"):
        try:
            record = APIKeyManager.get_instance().verify_api_key(token)
            user_id = record.owner_id
            tenant_id = getattr(record, "tenant_id", "default")
            role = "api_user"
            scopes = record.scopes
        except PermissionError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"API key verification failed: {e}",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

    # 3. Check JWT Token
    else:
        try:
            payload = jwt.decode(
                token,
                get_signing_secret(),
                algorithms=[ALGORITHM],
                options={"require": ["exp", "sub"]},
            )
            if payload.get("type", "access") != "access":
                raise InvalidTokenError("Only access tokens can authorize API requests")
            sub_id = payload.get("sub")
            if not isinstance(sub_id, str) or not sub_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload: missing sub claim.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            user_id = sub_id
            tenant_id = payload.get("tenant_id") or payload.get("org_id") or "default"

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

            role = payload.get("role", "user")
            scopes = payload.get("scopes", [])
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

    # Caller-supplied tenant escalation check
    if request is not None:
        caller_tenant = (
            request.headers.get("x-tenant-id")
            or request.query_params.get("tenant_id")
            or request.query_params.get("org_id")
        )
        if caller_tenant and caller_tenant != tenant_id:
            if role != "admin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Cross-tenant access violation: caller from tenant '{tenant_id}' cannot escalate to '{caller_tenant}'.",
                )
            tenant_id = caller_tenant

    # Bind active execution contexts for downstream components
    _current_tenant_var.set(tenant_id)
    _current_sender_id.set(user_id)

    return UserIdentity(
        user_id=user_id,
        tenant_id=tenant_id,
        role=role,
        scopes=scopes,
    )


async def require_auth_administrator(
    identity: UserIdentity = Depends(get_current_user),
) -> UserIdentity:
    if identity.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return identity
