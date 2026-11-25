"""Session-based Web Authentication Manager for AmberClaw Dashboard."""

import os
import secrets
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field


class WebSession(BaseModel):
    session_id: str = Field(repr=False)
    conversation_id: str = Field(
        default_factory=lambda: "wchat_" + secrets.token_hex(12)
    )
    user_id: str
    role: str
    created_at: datetime
    expires_at: datetime


class WebAuthManager:
    """Manages web dashboard authentication and session tokens."""

    def __init__(self, session_ttl_minutes: int = 480) -> None:
        self.session_ttl = timedelta(minutes=session_ttl_minutes)
        self._sessions: dict[str, WebSession] = {}

    def authenticate_credentials(self, username: str, password: str) -> bool:
        """Authenticate dashboard user credentials against environment defaults."""
        expected_user = os.getenv("WEB_ADMIN_USER")
        expected_pass = os.getenv("WEB_ADMIN_PASS")
        if not expected_user or not expected_pass:
            return False
        return secrets.compare_digest(
            username.encode("utf-8"), expected_user.encode("utf-8")
        ) and secrets.compare_digest(
            password.encode("utf-8"), expected_pass.encode("utf-8")
        )

    def create_session(self, user_id: str, role: str = "admin") -> WebSession:
        """Create a new authenticated web session."""
        now = datetime.now(UTC)
        session_id = f"wses_{secrets.token_hex(24)}"
        session = WebSession(
            session_id=session_id,
            user_id=user_id,
            role=role,
            created_at=now,
            expires_at=now + self.session_ttl,
        )
        self._sessions[session_id] = session
        return session

    def verify_session(self, session_id: str) -> WebSession | None:
        """Verify session token validity and expiration."""
        if not session_id or session_id not in self._sessions:
            return None
        session = self._sessions[session_id]
        if datetime.now(UTC) > session.expires_at:
            del self._sessions[session_id]
            return None
        return session

    def revoke_session(self, session_id: str) -> bool:
        """Revoke an active web session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False
