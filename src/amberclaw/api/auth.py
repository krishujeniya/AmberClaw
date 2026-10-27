"""API Authentication and Authorization dependencies."""

import os
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from amberclaw.security.tokens import APIKeyManager, TokenRevocationStore

# Secret key and algorithm for JWT tokens
JWT_SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY", "amberclaw-insecure-default-change-me-in-prod"
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# API key for service/automated calls
API_KEY = os.getenv("AMBERCLAW_API_KEY", "")

security_bearer = HTTPBearer(auto_error=False)


class TokenData(BaseModel):
    sub: str | None = None
    role: str = "user"
    scopes: list[str] = []


class UserIdentity(BaseModel):
    user_id: str
    role: str
    scopes: list[str] = []


def create_access_token(
    data: dict[str, Any], expires_delta: timedelta | None = None
) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)


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
    if API_KEY and token == API_KEY:
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
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
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
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
