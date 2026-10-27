"""Webhook signing, verification, and replay protection for AmberClaw API events.

Implements HMAC-SHA256 signature verification matching standard web security specs
with timestamp tolerance windows to prevent replay attacks.
"""

import hashlib
import hmac
import time

from loguru import logger


class WebhookSecurityError(PermissionError):
    """Raised when webhook signature verification fails."""


class WebhookSigner:
    """Signs outgoing webhook payloads using HMAC-SHA256."""

    def __init__(self, secret: str) -> None:
        self.secret = secret.encode("utf-8")

    def sign_payload(self, payload: str, timestamp: int | None = None) -> str:
        """Generate signature header in the format: t=<timestamp>,v1=<signature>."""
        t = timestamp if timestamp is not None else int(time.time())
        signed_content = f"{t}.{payload}".encode()
        signature = hmac.new(self.secret, signed_content, hashlib.sha256).hexdigest()
        return f"t={t},v1={signature}"


class WebhookVerifier:
    """Verifies incoming webhook payloads against signatures and replay tolerance windows."""

    def __init__(self, secret: str, tolerance_seconds: int = 300) -> None:
        self.secret = secret.encode("utf-8")
        self.tolerance_seconds = tolerance_seconds

    def verify_payload(self, payload: str, signature_header: str) -> bool:
        """Verify the signature and timestamp of an incoming webhook payload.

        Raises WebhookSecurityError if signature is invalid, missing, or outside tolerance.
        """
        if not signature_header:
            raise WebhookSecurityError("Missing webhook signature header")

        parts: dict[str, str] = {}
        for item in signature_header.split(","):
            if "=" in item:
                k, v = item.strip().split("=", 1)
                parts[k] = v

        timestamp_str = parts.get("t")
        received_signature = parts.get("v1")

        if not timestamp_str or not received_signature:
            raise WebhookSecurityError("Malformed webhook signature header")

        try:
            timestamp = int(timestamp_str)
        except ValueError as e:
            raise WebhookSecurityError(
                "Invalid timestamp in webhook signature header"
            ) from e

        # Replay attack prevention: check timestamp tolerance
        current_time = int(time.time())
        if abs(current_time - timestamp) > self.tolerance_seconds:
            logger.warning(
                "Webhook rejected: timestamp {} outside tolerance window", timestamp
            )
            raise WebhookSecurityError("Webhook timestamp outside tolerance window")

        # Compute expected signature
        signed_content = f"{timestamp}.{payload}".encode()
        expected_signature = hmac.new(
            self.secret, signed_content, hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(received_signature, expected_signature):
            logger.warning("Webhook rejected: invalid HMAC signature")
            raise WebhookSecurityError("Invalid webhook signature")

        return True
