# ruff: noqa: RUF012, PLR2004
"""Data Loss Prevention (DLP) Engine for AmberClaw.

Implements:
1. Multi-tier sensitivity scanning (API keys, private keys, financial numbers, system files).
2. Credit card detection with Luhn algorithm validation to minimize false positives.
3. Outbound data enforcement with configurable REDACT or BLOCK policies.
4. Cryptographically chained security audit logging on DLP events.
"""

import re
from enum import StrEnum
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.security.audit import AuditEvent, SecurityAuditLogger


class DLPSensitivity(StrEnum):
    """Sensitivity level of detected data."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DLPAction(StrEnum):
    """Action to enforce when sensitive data is detected."""

    ALLOW = "allow"
    REDACT = "redact"
    BLOCK = "block"


class DLPViolation(BaseModel):
    """Details of a single DLP violation."""

    pattern_type: str
    severity: DLPSensitivity
    matched_preview: str
    location: int


class DLPScanResult(BaseModel):
    """Consolidated outcome of a DLP scan."""

    has_violations: bool = False
    violations: list[DLPViolation] = Field(default_factory=list)
    action_taken: DLPAction = DLPAction.ALLOW
    clean_text: str = ""


class DLPViolationError(ValueError):
    """Raised when an outbound transmission is blocked by DLP policy."""


def _is_luhn_valid(number_str: str) -> bool:
    """Validate numeric string using the Luhn checksum algorithm."""
    digits = [int(c) for c in number_str if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False

    checksum = 0
    reverse_digits = digits[::-1]
    for i, digit in enumerate(reverse_digits):
        if i % 2 == 1:
            doubled = digit * 2
            checksum += (doubled - 9) if doubled > 9 else doubled
        else:
            checksum += digit
    return checksum % 10 == 0


class DataLossPreventionEngine:
    """Scans and enforces data protection policies on LLM inputs, tool outputs, and outbound messages."""

    # High-confidence credential and key patterns
    DLP_PATTERNS: list[dict[str, Any]] = [
        {
            "type": "private_key",
            "severity": DLPSensitivity.CRITICAL,
            "pattern": re.compile(
                r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]+?-----END [A-Z ]+ PRIVATE KEY-----"
            ),
        },
        {
            "type": "openai_api_key",
            "severity": DLPSensitivity.CRITICAL,
            "pattern": re.compile(
                r"\b(sk-[a-zA-Z0-9]{48,}|sk-proj-[a-zA-Z0-9_\-]{40,})\b"
            ),
        },
        {
            "type": "anthropic_api_key",
            "severity": DLPSensitivity.CRITICAL,
            "pattern": re.compile(r"\bsk-ant-[a-zA-Z0-9_\-]{30,}\b"),
        },
        {
            "type": "aws_access_key",
            "severity": DLPSensitivity.HIGH,
            "pattern": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        },
        {
            "type": "google_api_key",
            "severity": DLPSensitivity.HIGH,
            "pattern": re.compile(r"\bAIzaSy[a-zA-Z0-9_-]{33}\b"),
        },
        {
            "type": "github_token",
            "severity": DLPSensitivity.HIGH,
            "pattern": re.compile(r"\bgh[oprs]_[a-zA-Z0-9]{36,}\b"),
        },
        {
            "type": "slack_token",
            "severity": DLPSensitivity.HIGH,
            "pattern": re.compile(r"\bxox[baprs]-[a-zA-Z0-9-]{10,}\b"),
        },
        {
            "type": "system_shadow_entry",
            "severity": DLPSensitivity.CRITICAL,
            "pattern": re.compile(r"\broot:[*x!]:0:0:[^\n]+"),
        },
        {
            "type": "vault_token",
            "severity": DLPSensitivity.HIGH,
            "pattern": re.compile(r"\b(vault_[a-zA-Z0-9]{20,}|s\.[a-zA-Z0-9]{24,})\b"),
        },
        {
            "type": "ssn",
            "severity": DLPSensitivity.HIGH,
            "pattern": re.compile(
                r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"
            ),
        },
    ]

    # Credit card pattern candidate: 13 to 16 digits, with optional hyphens or spaces
    CARD_CANDIDATE_PATTERN = re.compile(r"\b(?:\d{4}[ -]?){3}\d{1,4}\b")

    @classmethod
    def scan(
        cls,
        text: str,
        default_action: DLPAction = DLPAction.REDACT,
    ) -> DLPScanResult:
        """Scan text for credentials, keys, financial data, and sensitive records."""
        if not text:
            return DLPScanResult(clean_text="")

        violations: list[DLPViolation] = []
        clean_text = text

        # 1. Match regex credential patterns
        for rule in cls.DLP_PATTERNS:
            p_type = rule["type"]
            severity = rule["severity"]
            pattern: re.Pattern = rule["pattern"]

            for match in pattern.finditer(text):
                val = match.group(0)
                preview = val[:4] + "..." + val[-4:] if len(val) > 12 else "[REDACTED]"
                violations.append(
                    DLPViolation(
                        pattern_type=p_type,
                        severity=severity,
                        matched_preview=preview,
                        location=match.start(),
                    )
                )

            # Redact in clean_text
            clean_text = pattern.sub(f"[DLP_REDACTED_{p_type.upper()}]", clean_text)

        # 2. Match financial cards using Luhn validation
        for match in cls.CARD_CANDIDATE_PATTERN.finditer(text):
            candidate = match.group(0)
            digits_only = re.sub(r"\D", "", candidate)
            if _is_luhn_valid(digits_only):
                preview = digits_only[:4] + "..." + digits_only[-4:]
                violations.append(
                    DLPViolation(
                        pattern_type="credit_card_number",
                        severity=DLPSensitivity.CRITICAL,
                        matched_preview=preview,
                        location=match.start(),
                    )
                )
                clean_text = clean_text.replace(candidate, "[DLP_REDACTED_CREDIT_CARD]")

        has_violations = len(violations) > 0
        action = default_action if has_violations else DLPAction.ALLOW

        return DLPScanResult(
            has_violations=has_violations,
            violations=violations,
            action_taken=action,
            clean_text=clean_text,
        )

    @classmethod
    def enforce_outbound(
        cls,
        content: str,
        destination: str = "outbound",
        block_on_critical: bool = True,
    ) -> str:
        """Scan outbound message or tool call and enforce REDACT or BLOCK policy."""
        scan_res = cls.scan(content)
        if not scan_res.has_violations:
            return content

        audit_logger = SecurityAuditLogger.get_logger()
        critical_violations = [
            v for v in scan_res.violations if v.severity == DLPSensitivity.CRITICAL
        ]

        # Check if we must block the request completely
        if block_on_critical and critical_violations:
            violation_types = [v.pattern_type for v in critical_violations]
            logger.error(
                "DLP blocked outbound dispatch to destination '{}'. Critical patterns: {}",
                destination,
                violation_types,
            )
            audit_logger.log_event(
                AuditEvent(
                    actor="dlp_engine",
                    action="dlp.outbound_blocked",
                    resource_type="outbound_message",
                    resource_id=destination,
                    outcome="blocked",
                    metadata={
                        "violation_types": violation_types,
                        "violation_count": len(scan_res.violations),
                    },
                )
            )
            raise DLPViolationError(
                f"DLP Policy Violation: Outbound transmission to '{destination}' blocked due to critical data leaks ({violation_types})."
            )

        # Otherwise redact secrets safely
        logger.warning(
            "DLP redacted {} sensitive data findings before dispatch to '{}'",
            len(scan_res.violations),
            destination,
        )
        audit_logger.log_event(
            AuditEvent(
                actor="dlp_engine",
                action="dlp.outbound_redacted",
                resource_type="outbound_message",
                resource_id=destination,
                outcome="redacted",
                metadata={
                    "violation_types": [v.pattern_type for v in scan_res.violations],
                    "violation_count": len(scan_res.violations),
                },
            )
        )
        return scan_res.clean_text


class ExternalTransmissionConfirmationError(DLPViolationError):
    """Raised when outbound private data transmission requires explicit human confirmation."""

    def __init__(
        self,
        message: str,
        destination: str,
        detected_patterns: list[str],
        confirmation_challenge: str,
    ) -> None:
        super().__init__(message)
        self.destination = destination
        self.detected_patterns = detected_patterns
        self.confirmation_challenge = confirmation_challenge


class ExternalTransmissionGuard:
    """Guards external transmission of private or confidential data by enforcing human confirmation."""

    _valid_tokens: dict[str, float] = {}  # token -> expiry_timestamp

    @classmethod
    def issue_confirmation_token(
        cls, _challenge: str = "", ttl_seconds: float = 300.0
    ) -> str:
        """Issues an approval confirmation token for transmitting detected sensitive data."""
        import secrets  # noqa: PLC0415
        import time  # noqa: PLC0415

        token = f"dlp_conf_{secrets.token_hex(16)}"
        cls._valid_tokens[token] = time.time() + ttl_seconds
        return token

    @classmethod
    def check_transmission(
        cls,
        content: str,
        destination: str,
        requires_confirmation: bool = True,
        confirmation_token: str | None = None,
    ) -> str:
        """Verifies outbound content and requires explicit confirmation if sensitive data is detected."""
        import time  # noqa: PLC0415

        scan_res = DataLossPreventionEngine.scan(content)
        if not scan_res.has_violations:
            return content

        patterns = [v.pattern_type for v in scan_res.violations]

        if requires_confirmation:
            now = time.time()
            if not confirmation_token or confirmation_token not in cls._valid_tokens:
                challenge = f"confirm_send_{destination}_{len(patterns)}"
                raise ExternalTransmissionConfirmationError(
                    f"External transmission to '{destination}' contains private/sensitive data ({patterns}). "
                    "Explicit operator confirmation is required.",
                    destination=destination,
                    detected_patterns=patterns,
                    confirmation_challenge=challenge,
                )

            # Check token expiration
            if cls._valid_tokens[confirmation_token] < now:
                del cls._valid_tokens[confirmation_token]
                raise ExternalTransmissionConfirmationError(
                    "Confirmation token has expired",
                    destination=destination,
                    detected_patterns=patterns,
                    confirmation_challenge="",
                )

            # Consume token
            del cls._valid_tokens[confirmation_token]

            # Audit confirmation
            audit_logger = SecurityAuditLogger.get_logger()
            audit_logger.log_event(
                AuditEvent(
                    actor="operator",
                    action="security.dlp.outbound_transmission_confirmed",
                    resource_type="external_dispatch",
                    resource_id=destination,
                    outcome="confirmed",
                    metadata={
                        "destination": destination,
                        "patterns": patterns,
                    },
                )
            )

        return content
