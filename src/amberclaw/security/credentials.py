"""Explicit authentication configuration shared by token issuers and verifiers."""

import hmac
import os

MIN_SECRET_BYTES = 32
LEGACY_SIGNING_DEFAULT = "amberclaw-insecure-default-change-me-in-prod"


class AuthenticationConfigurationError(RuntimeError):
    """Authentication cannot run without an explicitly configured secret."""


def validate_signing_secret(secret: str) -> str:
    if len(secret.encode()) < MIN_SECRET_BYTES or hmac.compare_digest(
        secret, LEGACY_SIGNING_DEFAULT
    ):
        raise AuthenticationConfigurationError(
            "JWT_SECRET_KEY must be an explicit random secret of at least 32 bytes"
        )
    return secret


def get_signing_secret() -> str:
    return validate_signing_secret(os.environ.get("JWT_SECRET_KEY", ""))


def get_client_credentials() -> tuple[str, str]:
    client_id = os.environ.get("AUTH_CLIENT_ID", "")
    secret = os.environ.get("AUTH_CLIENT_SECRET", "")
    if not client_id or len(secret.encode()) < MIN_SECRET_BYTES:
        raise AuthenticationConfigurationError(
            "Explicit AUTH_CLIENT_ID and a random AUTH_CLIENT_SECRET of at least 32 bytes are required"
        )
    return client_id, secret
