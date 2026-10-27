"""Exceptions for the AmberClaw Python Client SDK."""

from typing import Any


class AmberClawSDKError(Exception):
    """Base exception for all AmberClaw SDK errors."""


class AmberClawConnectionError(AmberClawSDKError):
    """Raised when communication with the AmberClaw Gateway fails."""


class AmberClawAuthError(AmberClawSDKError):
    """Raised when authentication credentials (Bearer JWT or API key) are rejected."""


class AmberClawAPIError(AmberClawSDKError):
    """Raised when the AmberClaw API returns an error envelope."""

    def __init__(
        self,
        message: str,
        code: str = "API_ERROR",
        status_code: int = 500,
        request_id: str | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(f"[{code}] {message} (status: {status_code})")
        self.message = message
        self.code = code
        self.status_code = status_code
        self.request_id = request_id
        self.details = details
