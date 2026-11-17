# ruff: noqa: PLR0913, PTH123, PLW2901
"""AmberClaw Security Audit Logging System.

Provides structured, PII/secret-scrubbed, cryptographically verifiable event logging
for all agent execution, authorization, secret access, and governance operations.
"""

import contextlib
import hashlib
import hmac
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field

# Pattern list for redacting sensitive credentials and PII
SECRET_PATTERNS = [
    re.compile(
        r"(?i)(api[_\-\s]?key|secret(\s+key)?|password|passwd|token|auth|bearer)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?"
    ),
    re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]{8,}", re.IGNORECASE),
    re.compile(r"sk-[a-zA-Z0-9_\-]{20,}", re.IGNORECASE),
    re.compile(
        r"-----BEGIN\s+[A-Z\s]+PRIVATE\s+KEY-----[\s\S]+?-----END\s+[A-Z\s]+PRIVATE\s+KEY-----"
    ),
]


def redact_secrets(data: Any) -> Any:
    """Recursively scrub secrets, API keys, and sensitive tokens from metadata dictionary/strings."""
    if isinstance(data, str):
        cleaned = data
        for pattern in SECRET_PATTERNS:
            cleaned = pattern.sub("[REDACTED_SECRET]", cleaned)
        return cleaned
    if isinstance(data, dict):
        cleaned_dict = {}
        for k, v in data.items():
            if any(
                term in k.lower()
                for term in [
                    "password",
                    "secret",
                    "token",
                    "api_key",
                    "apikey",
                    "private_key",
                    "authorization",
                ]
            ):
                cleaned_dict[k] = "[REDACTED_SECRET]"
            else:
                cleaned_dict[k] = redact_secrets(v)
        return cleaned_dict
    if isinstance(data, list):
        return [redact_secrets(item) for item in data]
    return data


class AuditEvent(BaseModel):
    """Pydantic schema for structured audit events."""

    actor: str = Field(
        default="system",
        description="User, service, or agent ID initiating the action",
    )
    tenant: str = Field(
        default="default", description="Tenant or organization identifier"
    )
    action: str = Field(
        ...,
        description="Action name (e.g., agent.create, tool.execute, secret.read)",
    )
    resource_type: str = Field(
        default="unknown", description="Type of resource affected"
    )
    resource_id: str = Field(default="unknown", description="ID of resource affected")
    outcome: str = Field(
        default="success", description="Outcome: success, failure, denied"
    )
    timestamp_utc: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    correlation_id: str = Field(default="", description="Trace or correlation ID")
    integrity_proof: str = Field(
        default="", description="Cryptographic SHA-256 hash proof"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional context fields"
    )


@contextlib.contextmanager
def _audit_file_lock(lock_path: Path):
    """Cross-process advisory lock for serialized audit transactions."""
    lock_file = open(lock_path, "a+", encoding="utf-8")
    try:
        if sys.platform != "win32":
            import fcntl  # noqa: PLC0415

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        if sys.platform != "win32":
            import fcntl  # noqa: PLC0415

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()


class AuditAnchorReceipt(BaseModel):
    """Cryptographic external anchor receipt attesting to chain state up to a fixed index."""

    anchor_index: int
    anchor_hash: str
    record_count: int
    timestamp_utc: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    anchor_id: str = Field(
        default_factory=lambda: hashlib.sha256(
            datetime.now(UTC).isoformat().encode()
        ).hexdigest()[:16]
    )


class SecurityAuditLogger:
    """Structured event audit logger with tamper-evident SHA-256 hash chaining."""

    _default_instance: Optional["SecurityAuditLogger"] = None

    def __init__(self, log_dir: str | Path = "logs") -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "audit.jsonl"
        self.lock_file = self.log_dir / ".audit.lock"

    @classmethod
    def get_logger(cls, log_dir: str | Path = "logs") -> "SecurityAuditLogger":
        """Get singleton or default instance of the audit logger."""
        if cls._default_instance is None:
            cls._default_instance = cls(log_dir)
        return cls._default_instance

    def _calculate_hash(
        self,
        index: int,
        timestamp: str,
        actor: str,
        action: str,
        details_str: str,
        previous_hash: str,
    ) -> str:
        payload = f"{index}|{timestamp}|{actor}|{action}|{details_str}|{previous_hash}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _get_last_entry(self) -> tuple[int, str]:
        if not self.log_file.exists() or self.log_file.stat().st_size == 0:
            return -1, "0" * 64
        try:
            with open(self.log_file, encoding="utf-8") as f:
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - 4096))
                lines = f.readlines()
                if lines:
                    last_line = lines[-1].strip()
                    if last_line:
                        data = json.loads(last_line)
                        return data.get("index", 0), data.get(
                            "integrity_proof", data.get("hash", "0" * 64)
                        )
        except Exception as e:
            logger.error("Failed to read last entry from security audit log: {}", e)
        return -1, "0" * 64

    def log_event(
        self,
        action: str | AuditEvent,
        actor: str = "system",
        tenant: str = "default",
        resource_type: str = "unknown",
        resource_id: str = "unknown",
        outcome: str = "success",
        correlation_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Log a structured audit event to the append-only jsonl log with SHA-256 chaining."""
        if isinstance(action, AuditEvent):
            event = action
            action_name = event.action
            actor = event.actor
            tenant = event.tenant
            resource_type = event.resource_type
            resource_id = event.resource_id
            outcome = event.outcome
            correlation_id = event.correlation_id
            clean_metadata = redact_secrets(event.metadata or {})
        else:
            action_name = action
            clean_metadata = redact_secrets(metadata or {})
        with _audit_file_lock(self.lock_file):
            last_index, previous_hash = self._get_last_entry()
            next_index = last_index + 1
            timestamp = datetime.now(UTC).isoformat()

            details_str = json.dumps(
                {
                    "tenant": tenant,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "outcome": outcome,
                    "correlation_id": correlation_id,
                    "metadata": clean_metadata,
                },
                sort_keys=True,
            )

            proof = self._calculate_hash(
                next_index, timestamp, actor, action_name, details_str, previous_hash
            )

            event = AuditEvent(
                actor=actor,
                tenant=tenant,
                action=action_name,
                resource_type=resource_type,
                resource_id=resource_id,
                outcome=outcome,
                timestamp_utc=timestamp,
                correlation_id=correlation_id,
                integrity_proof=proof,
                metadata=clean_metadata,
            )

            log_payload = event.model_dump()
            log_payload["index"] = next_index
            log_payload["previous_hash"] = previous_hash
            log_payload["hash"] = proof

            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_payload) + "\n")
                f.flush()
                os.fsync(f.fileno())

        logger.debug(
            "Security audit log entry created: actor={} action={} outcome={} index={}",
            actor,
            action,
            outcome,
            next_index,
        )
        return event

    def create_anchor_receipt(self) -> AuditAnchorReceipt:
        """Create a cryptographic receipt of current log state to detect truncation."""
        last_index, last_hash = self._get_last_entry()
        receipt = AuditAnchorReceipt(
            anchor_index=last_index,
            anchor_hash=last_hash,
            record_count=last_index + 1 if last_index >= 0 else 0,
        )
        anchor_file = self.log_dir / "audit_anchor.json"
        anchor_file.write_text(receipt.model_dump_json(indent=2), encoding="utf-8")
        return receipt

    def export_event_receipt(self, event: AuditEvent) -> dict[str, Any]:
        """Export a portable, redacted cryptographic receipt for a specific event."""
        return {
            "receipt_version": "1.0.0",
            "actor": event.actor,
            "tenant": event.tenant,
            "action": event.action,
            "resource_type": event.resource_type,
            "resource_id": event.resource_id,
            "outcome": event.outcome,
            "timestamp_utc": event.timestamp_utc,
            "correlation_id": event.correlation_id,
            "integrity_proof": event.integrity_proof,
            "metadata": redact_secrets(event.metadata),
        }

    def verify_receipt(self, receipt: dict[str, Any]) -> bool:
        """Verify an exported receipt matches an entry in the local tamper-evident log."""
        if not self.log_file.exists():
            return False
        proof = receipt.get("integrity_proof")
        if not proof:
            return False
        with open(self.log_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                if hmac.compare_digest(
                    str(data.get("integrity_proof", data.get("hash", ""))),
                    str(proof),
                ):
                    return True
        return False

    def verify_integrity(
        self,
        target_file: Path | None = None,
        expected_anchor: AuditAnchorReceipt | None = None,
    ) -> bool:
        """Verify the cryptographic integrity of the security audit log file."""
        log_file = target_file or self.log_file
        if not log_file.exists():
            return True

        try:
            expected_prev_hash = "0" * 64
            expected_index = 0
            last_seen_hash = "0" * 64
            last_seen_index = -1

            with open(log_file, encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    data = json.loads(line)
                    idx = data.get("index")
                    if idx != expected_index:
                        logger.error(
                            "Audit log verification failed line {}: expected index {}, got {}",
                            line_num,
                            expected_index,
                            idx,
                        )
                        return False

                    prev_hash = data.get("previous_hash")
                    if not hmac.compare_digest(
                        str(prev_hash or ""), str(expected_prev_hash or "")
                    ):
                        logger.error(
                            "Audit log verification failed line {}: expected prev_hash {}, got {}",
                            line_num,
                            expected_prev_hash,
                            prev_hash,
                        )
                        return False

                    timestamp = data.get("timestamp_utc", data.get("timestamp", ""))
                    actor = data.get("actor", data.get("agent_id", ""))
                    action = data.get("action", "")
                    clean_metadata = data.get("metadata", {})

                    details_str = json.dumps(
                        {
                            "tenant": data.get("tenant", "default"),
                            "resource_type": data.get("resource_type", "unknown"),
                            "resource_id": data.get("resource_id", "unknown"),
                            "outcome": data.get("outcome", "success"),
                            "correlation_id": data.get("correlation_id", ""),
                            "metadata": clean_metadata,
                        },
                        sort_keys=True,
                    )

                    current_hash = data.get("integrity_proof", data.get("hash"))
                    recalculated = self._calculate_hash(
                        idx, timestamp, actor, action, details_str, prev_hash
                    )

                    if not hmac.compare_digest(
                        str(current_hash or ""), str(recalculated or "")
                    ):
                        logger.error(
                            "Audit log verification failed line {}: hash mismatch",
                            line_num,
                        )
                        return False

                    last_seen_hash = current_hash
                    last_seen_index = idx
                    expected_prev_hash = current_hash
                    expected_index += 1

            if expected_anchor is not None:
                if last_seen_index != expected_anchor.anchor_index:
                    logger.error(
                        "Audit log truncation detected: expected anchor index {}, got {}",
                        expected_anchor.anchor_index,
                        last_seen_index,
                    )
                    return False
                if not hmac.compare_digest(
                    str(last_seen_hash), str(expected_anchor.anchor_hash)
                ):
                    logger.error(
                        "Audit log anchor hash mismatch: expected {}, got {}",
                        expected_anchor.anchor_hash,
                        last_seen_hash,
                    )
                    return False

            return True
        except Exception as e:
            logger.error("Error verifying security audit log chain: {}", e)
            return False


# Global default security audit logger
security_auditor = SecurityAuditLogger()
