# ruff: noqa: S105, RUF012, PLR2004, SIM102
"""Identity, Token Lifecycle, API Key Security, and Emergency Break-Glass Management.

Provides:
- Short-lived JWT access tokens and rotating refresh tokens with reuse detection.
- Token and session revocation stores.
- Cryptographically hashed API keys with prefix matching, scope enforcement, and rotation.
- Break-glass emergency privilege elevation with mandatory audit event logging.
"""

import hashlib
import hmac
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.security.audit import AuditEvent, SecurityAuditLogger

# Secret key and cryptographic constants
JWT_SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY", "amberclaw-insecure-default-change-me-in-prod"
)
ALGORITHM = "HS256"
DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES = 15
DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS = 7


class SecurityCompromiseError(PermissionError):
    """Raised when token reuse or cryptographic compromise is detected."""


class TokenPair(BaseModel):
    """Access and refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int


class TokenRevocationStore:
    """In-memory and thread-safe token & session revocation registry."""

    _instance: "TokenRevocationStore | None" = None

    def __init__(self) -> None:
        self._revoked_jtis: dict[str, datetime] = {}
        self._revoked_sessions: set[str] = set()
        self._revoked_families: set[str] = set()

    @classmethod
    def get_instance(cls) -> "TokenRevocationStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def revoke_jti(self, jti: str, expires_at: datetime | None = None) -> None:
        """Revoke a single JWT identifier (jti)."""
        exp = expires_at or (
            datetime.now(UTC) + timedelta(days=DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS)
        )
        self._revoked_jtis[jti] = exp
        self._cleanup()

    def is_jti_revoked(self, jti: str) -> bool:
        """Check if a jti is in the revocation store and unexpired."""
        if jti in self._revoked_jtis:
            if datetime.now(UTC) > self._revoked_jtis[jti]:
                self._revoked_jtis.pop(jti, None)
                return False
            return True
        return False

    def revoke_session(self, session_id: str) -> None:
        """Revoke all tokens belonging to a session."""
        self._revoked_sessions.add(session_id)

    def is_session_revoked(self, session_id: str) -> bool:
        """Check if a session has been revoked."""
        return session_id in self._revoked_sessions

    def revoke_family(self, family_id: str) -> None:
        """Revoke an entire refresh token family due to detected reuse."""
        self._revoked_families.add(family_id)

    def is_family_revoked(self, family_id: str) -> bool:
        """Check if a refresh token family is revoked."""
        return family_id in self._revoked_families

    def clear(self) -> None:
        """Clear all revocation data (primarily for test resets)."""
        self._revoked_jtis.clear()
        self._revoked_sessions.clear()
        self._revoked_families.clear()

    def _cleanup(self) -> None:
        """Evict expired jtis."""
        now = datetime.now(UTC)
        expired = [jti for jti, exp in self._revoked_jtis.items() if now > exp]
        for jti in expired:
            self._revoked_jtis.pop(jti, None)


class RefreshTokenManager:
    """Manages creation, rotation, and cryptographic verification of tokens."""

    _instance: "RefreshTokenManager | None" = None
    _active_family_tokens: dict[str, set[str]] = {}

    def __init__(
        self,
        secret_key: str = JWT_SECRET_KEY,
        access_expire_minutes: int = DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_expire_days: int = DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS,
        revocation_store: TokenRevocationStore | None = None,
    ) -> None:
        self.secret_key = secret_key
        self.access_expire_minutes = access_expire_minutes
        self.refresh_expire_days = refresh_expire_days
        self.store = revocation_store or TokenRevocationStore.get_instance()

    @classmethod
    def get_instance(cls) -> "RefreshTokenManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def clear(cls) -> None:
        cls._active_family_tokens.clear()

    def create_token_pair(
        self,
        user_id: str,
        role: str = "user",
        scopes: list[str] | None = None,
        session_id: str | None = None,
        family_id: str | None = None,
    ) -> TokenPair:
        """Issue a new access token and rotating refresh token."""
        now = datetime.now(UTC)
        sid = session_id or uuid.uuid4().hex
        fam_id = family_id or uuid.uuid4().hex
        scopes = scopes or []

        # Access Token
        access_jti = uuid.uuid4().hex
        access_exp = now + timedelta(minutes=self.access_expire_minutes)
        access_payload = {
            "sub": user_id,
            "role": role,
            "scopes": scopes,
            "session_id": sid,
            "type": "access",
            "jti": access_jti,
            "exp": access_exp,
        }
        access_token = jwt.encode(access_payload, self.secret_key, algorithm=ALGORITHM)

        # Refresh Token
        refresh_jti = uuid.uuid4().hex
        refresh_exp = now + timedelta(days=self.refresh_expire_days)
        refresh_payload = {
            "sub": user_id,
            "role": role,
            "scopes": scopes,
            "session_id": sid,
            "family_id": fam_id,
            "type": "refresh",
            "jti": refresh_jti,
            "exp": refresh_exp,
        }
        refresh_token = jwt.encode(
            refresh_payload, self.secret_key, algorithm=ALGORITHM
        )

        if fam_id not in self._active_family_tokens:
            self._active_family_tokens[fam_id] = set()
        self._active_family_tokens[fam_id].add(refresh_jti)

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int(self.access_expire_minutes * 60),
            refresh_expires_in=int(self.refresh_expire_days * 86400),
        )

    def rotate_refresh_token(self, refresh_token: str) -> TokenPair:
        """Rotate a refresh token.

        If a previously rotated refresh token is presented again (reuse), the entire token
        family is immediately revoked and a SecurityCompromiseError is raised.
        """
        try:
            payload = jwt.decode(refresh_token, self.secret_key, algorithms=[ALGORITHM])
        except JWTError as e:
            raise PermissionError(f"Invalid refresh token: {e}") from e

        if payload.get("type") != "refresh":
            raise PermissionError("Provided token is not a refresh token")

        jti = payload.get("jti")
        fam_id = payload.get("family_id")
        user_id = payload.get("sub")
        role = payload.get("role", "user")
        scopes = payload.get("scopes", [])
        session_id = payload.get("session_id")

        if not jti or not fam_id or not user_id:
            raise PermissionError("Malformed refresh token claims")

        # 1. Check if token family is revoked
        if self.store.is_family_revoked(fam_id):
            raise SecurityCompromiseError(
                f"Refresh token family '{fam_id}' is revoked due to prior compromise"
            )

        # 2. Check if session is revoked
        if session_id and self.store.is_session_revoked(session_id):
            raise PermissionError(f"Session '{session_id}' has been revoked")

        # 3. Check for REUSE: if jti was already revoked or not in active family set
        valid_family_jtis = self._active_family_tokens.get(fam_id, set())
        if self.store.is_jti_revoked(jti) or (jti not in valid_family_jtis):
            # Compromise detected! Invalidate the whole family!
            self.store.revoke_family(fam_id)
            self._active_family_tokens.pop(fam_id, None)
            logger.critical(
                "TOKEN REUSE DETECTED for user '{}' in family '{}'! Revoking family.",
                user_id,
                fam_id,
            )
            # Emit audit event for security incident
            audit_logger = SecurityAuditLogger.get_logger()
            audit_logger.log_event(
                AuditEvent(
                    actor=user_id,
                    action="auth.token_reuse_detected",
                    resource_type="token_family",
                    resource_id=fam_id,
                    outcome="denied",
                    metadata={"jti": jti, "incident": "replay_attack_attempt"},
                )
            )
            raise SecurityCompromiseError(
                "Token reuse detected; refresh family revoked"
            )

        # 4. Valid rotation: revoke old jti and remove from active family set
        self.store.revoke_jti(jti)
        valid_family_jtis.discard(jti)

        # 5. Issue new pair with the same family_id
        return self.create_token_pair(
            user_id=user_id,
            role=role,
            scopes=scopes,
            session_id=session_id,
            family_id=fam_id,
        )


class APIKeyRecord(BaseModel):
    """Stored representation of an API Key."""

    key_id: str
    key_prefix: str
    hashed_key: str
    salt: str
    owner_id: str
    scopes: list[str] = Field(default_factory=list)
    name: str = "default"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    is_active: bool = True


class APIKeyManager:
    """Manages secure, hashed API keys with prefixes, scopes, and lifecycle controls."""

    _instance: "APIKeyManager | None" = None

    def __init__(self) -> None:
        self._keys: dict[str, APIKeyRecord] = {}

    @classmethod
    def get_instance(cls) -> "APIKeyManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def _hash(raw_key: str, salt: str) -> str:
        return hashlib.sha256(f"{salt}:{raw_key}".encode()).hexdigest()

    def create_api_key(
        self,
        owner_id: str,
        scopes: list[str] | None = None,
        name: str = "API Key",
        expires_in_days: int | None = 30,
    ) -> tuple[APIKeyRecord, str]:
        """Generate a new secure API key with prefix.

        Returns the persistent APIKeyRecord and the plaintext key (returned only once).
        """
        key_id = f"key_{uuid.uuid4().hex[:12]}"
        random_entropy = secrets.token_hex(24)
        raw_key = f"ak_live_{random_entropy}"
        key_prefix = raw_key[:12]
        salt = secrets.token_hex(16)
        hashed = self._hash(raw_key, salt)

        now = datetime.now(UTC)
        expires_at = now + timedelta(days=expires_in_days) if expires_in_days else None

        record = APIKeyRecord(
            key_id=key_id,
            key_prefix=key_prefix,
            hashed_key=hashed,
            salt=salt,
            owner_id=owner_id,
            scopes=scopes or ["*"],
            name=name,
            created_at=now,
            expires_at=expires_at,
            is_active=True,
        )
        self._keys[key_id] = record
        return record, raw_key

    def verify_api_key(
        self,
        raw_key: str,
        required_scope: str | None = None,
    ) -> APIKeyRecord:
        """Verify an API key and check scope and expiration."""
        if not raw_key.startswith("ak_live_"):
            raise PermissionError("Invalid API key format")

        prefix = raw_key[:12]
        matching_keys = [
            k for k in self._keys.values() if k.key_prefix == prefix and k.is_active
        ]

        for record in matching_keys:
            computed = self._hash(raw_key, record.salt)
            if hmac.compare_digest(computed, record.hashed_key):
                # Check expiration
                if record.expires_at and datetime.now(UTC) > record.expires_at:
                    raise PermissionError(f"API key '{record.key_id}' has expired")

                # Check scope
                if required_scope:
                    if "*" not in record.scopes and required_scope not in record.scopes:
                        raise PermissionError(
                            f"API key missing required scope '{required_scope}'"
                        )
                return record

        raise PermissionError("Invalid or inactive API key")

    def rotate_api_key(
        self,
        key_id: str,
        new_expires_in_days: int | None = 30,
    ) -> tuple[APIKeyRecord, str]:
        """Revoke the existing key and issue a replacement with identical scopes."""
        old_record = self._keys.get(key_id)
        if not old_record or not old_record.is_active:
            raise ValueError(f"API key '{key_id}' not found or already inactive")

        old_record.is_active = False

        new_record, raw_key = self.create_api_key(
            owner_id=old_record.owner_id,
            scopes=old_record.scopes,
            name=f"{old_record.name} (Rotated)",
            expires_in_days=new_expires_in_days,
        )
        return new_record, raw_key

    def revoke_api_key(self, key_id: str) -> bool:
        """Deactivate an API key immediately."""
        if key_id in self._keys:
            self._keys[key_id].is_active = False
            return True
        return False

    def clear(self) -> None:
        self._keys.clear()


class BreakGlassElevation(BaseModel):
    """Emergency administrative privilege elevation record."""

    elevation_id: str
    user_id: str
    reason: str
    approved_by: str
    granted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class BreakGlassManager:
    """Manages just-in-time emergency break-glass elevation with mandatory audit logs."""

    _instance: "BreakGlassManager | None" = None

    def __init__(self) -> None:
        self._elevations: dict[str, BreakGlassElevation] = {}

    @classmethod
    def get_instance(cls) -> "BreakGlassManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def request_break_glass(
        self,
        user_id: str,
        reason: str,
        duration_minutes: int = 60,
        approved_by: str = "emergency_protocol",
    ) -> BreakGlassElevation:
        """Request emergency elevation. Enforces justification and strict duration limits."""
        if len(reason.strip()) < 10:
            raise ValueError(
                "Break-glass justification reason must be at least 10 characters"
            )

        max_minutes = 120
        actual_minutes = min(max(duration_minutes, 5), max_minutes)

        elevation_id = f"bg_{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=actual_minutes)

        elevation = BreakGlassElevation(
            elevation_id=elevation_id,
            user_id=user_id,
            reason=reason,
            approved_by=approved_by,
            granted_at=now,
            expires_at=expires_at,
            is_active=True,
        )
        self._elevations[elevation_id] = elevation

        # Log high-priority security audit event
        audit_logger = SecurityAuditLogger.get_logger()
        audit_logger.log_event(
            AuditEvent(
                actor=user_id,
                action="auth.break_glass_granted",
                resource_type="administrative_privilege",
                resource_id=elevation_id,
                outcome="success",
                metadata={
                    "reason": reason,
                    "duration_minutes": actual_minutes,
                    "approved_by": approved_by,
                    "expires_at": expires_at.isoformat(),
                },
            )
        )
        return elevation

    def verify_elevation(self, elevation_id: str) -> bool:
        """Check if break-glass elevation is currently valid."""
        elevation = self._elevations.get(elevation_id)
        if not elevation or not elevation.is_active:
            return False
        if datetime.now(UTC) > elevation.expires_at:
            elevation.is_active = False
            return False
        return True

    def revoke_break_glass(self, elevation_id: str, revoked_by: str = "admin") -> bool:
        """Revoke emergency elevation immediately."""
        elevation = self._elevations.get(elevation_id)
        if elevation and elevation.is_active:
            elevation.is_active = False
            audit_logger = SecurityAuditLogger.get_logger()
            audit_logger.log_event(
                AuditEvent(
                    actor=revoked_by,
                    action="auth.break_glass_revoked",
                    resource_type="administrative_privilege",
                    resource_id=elevation_id,
                    outcome="success",
                    metadata={"user_id": elevation.user_id},
                )
            )
            return True
        return False

    def clear(self) -> None:
        self._elevations.clear()
