"""Bounded single-process, browser-bound, single-use SSO login requests."""

import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from amberclaw.security.sso.models import SSOConfig

LOGIN_TTL = 300
MAX_PENDING_LOGINS = 1024
SSO_COOKIE = "amberclaw_sso_request"


@dataclass
class PendingLogin:
    config: SSOConfig
    request_id: str = ""
    nonce: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    verifier: str = field(default_factory=lambda: secrets.token_urlsafe(48))
    metadata: dict[str, Any] = field(default_factory=dict)
    expires: float = field(default_factory=lambda: time.monotonic() + LOGIN_TTL)


class LoginRequests:
    """Ephemeral process-local requests; restarts fail closed, never bypass state."""

    def __init__(self) -> None:
        self._pending: dict[str, PendingLogin] = {}

    def create(self, config: SSOConfig) -> tuple[str, PendingLogin]:
        self._pending = {
            key: login
            for key, login in self._pending.items()
            if login.expires > time.monotonic()
        }
        if len(self._pending) >= MAX_PENDING_LOGINS:
            raise ValueError("Too many pending SSO logins")
        state = secrets.token_urlsafe(32)
        login = PendingLogin(config.model_copy(deep=True))
        self._pending[state] = login
        return state, login

    def consume(self, state: str, cookie: str) -> PendingLogin:
        if not state or not cookie or not secrets.compare_digest(state, cookie):
            raise ValueError("SSO browser state mismatch")
        login = self._pending.pop(state, None)
        if login is None or login.expires <= time.monotonic():
            raise ValueError("SSO request expired or already consumed")
        return login

    def clear(self) -> None:
        self._pending.clear()
