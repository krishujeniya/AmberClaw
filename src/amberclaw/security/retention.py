"""Data retention, compliance deletion, legal hold, and export manager.

Enforces GDPR/CCPA compliance, automated record expiration (TTL),
evidentiary legal hold safeguards, and tamper-evident data exports.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from amberclaw.security.audit import AuditEvent, SecurityAuditLogger

logger = logging.getLogger(__name__)


class LegalHoldActiveError(PermissionError):
    """Raised when data deletion or purge is attempted on an entity subject to an active legal hold."""


class LegalHoldRecord(BaseModel):
    """Evidentiary legal hold record preserving data from expiration or deletion."""

    entity_type: str  # e.g., "user", "session", "workspace", "tenant"
    entity_id: str
    reason: str
    placed_by: str
    placed_at: float = Field(default_factory=time.time)
    active: bool = True


class RetentionPolicy(BaseModel):
    """Retention rule configuration for a specific data domain."""

    category: str  # e.g., "chat_turns", "audit_logs", "ephemeral_files"
    ttl_days: int = Field(
        default=90, description="Time-to-live in days before record expiration"
    )
    enforce_legal_hold: bool = True


class DataRetentionManager:
    """Coordinates lifecycle data expiration, legal holds, and GDPR/CCPA exports."""

    def __init__(self) -> None:
        self._legal_holds: dict[tuple[str, str], LegalHoldRecord] = {}
        self._audit_logger = SecurityAuditLogger.get_logger()

    def set_legal_hold(
        self,
        entity_type: str,
        entity_id: str,
        reason: str,
        placed_by: str,
    ) -> LegalHoldRecord:
        """Places an evidentiary legal hold preventing deletion or purging."""
        key = (entity_type.lower(), entity_id)
        hold = LegalHoldRecord(
            entity_type=entity_type.lower(),
            entity_id=entity_id,
            reason=reason,
            placed_by=placed_by,
            active=True,
        )
        self._legal_holds[key] = hold
        logger.warning(
            "LEGAL HOLD PLACED on %s '%s' by %s. Reason: %s",
            entity_type,
            entity_id,
            placed_by,
            reason,
        )
        self._audit_logger.log_event(
            AuditEvent(
                actor=placed_by,
                action="security.legal_hold.placed",
                resource_type=entity_type,
                resource_id=entity_id,
                outcome="success",
                metadata={"reason": reason},
            )
        )
        return hold

    def release_legal_hold(
        self,
        entity_type: str,
        entity_id: str,
        released_by: str,
        reason: str = "Investigation concluded",
    ) -> bool:
        """Releases an active legal hold."""
        key = (entity_type.lower(), entity_id)
        if key not in self._legal_holds or not self._legal_holds[key].active:
            return False

        self._legal_holds[key].active = False
        logger.info(
            "LEGAL HOLD RELEASED on %s '%s' by %s. Reason: %s",
            entity_type,
            entity_id,
            released_by,
            reason,
        )
        self._audit_logger.log_event(
            AuditEvent(
                actor=released_by,
                action="security.legal_hold.released",
                resource_type=entity_type,
                resource_id=entity_id,
                outcome="success",
                metadata={"reason": reason},
            )
        )
        return True

    def is_under_legal_hold(self, entity_type: str, entity_id: str) -> bool:
        """Checks if a given entity is currently protected under an active legal hold."""
        key = (entity_type.lower(), entity_id)
        return key in self._legal_holds and self._legal_holds[key].active

    def purge_expired_records(
        self,
        records: list[dict[str, Any]],
        timestamp_field: str = "timestamp",
        ttl_days: int = 30,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Filters expired records outside the TTL window, blocking purge if under legal hold."""
        if (
            entity_type
            and entity_id
            and self.is_under_legal_hold(entity_type, entity_id)
        ):
            logger.info(
                "Skipping retention purge for %s '%s' due to active legal hold",
                entity_type,
                entity_id,
            )
            return records, 0

        now = time.time()
        cutoff = now - (ttl_days * 86400)
        retained: list[dict[str, Any]] = []
        purged_count = 0

        for r in records:
            ts = r.get(timestamp_field, now)
            if ts < cutoff:
                purged_count += 1
            else:
                retained.append(r)

        return retained, purged_count

    def export_compliance_archive(
        self,
        user_id: str,
        datasets: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        """Generates a tamper-evident GDPR/CCPA data portability package with checksums."""
        manifest: dict[str, str] = {}
        for category, records in datasets.items():
            serialized = json.dumps(records, sort_keys=True).encode("utf-8")
            manifest[category] = hashlib.sha256(serialized).hexdigest()

        overall_hash = hashlib.sha256(
            json.dumps(manifest, sort_keys=True).encode("utf-8")
        ).hexdigest()

        archive = {
            "user_id": user_id,
            "exported_at": time.time(),
            "manifest_sha256": manifest,
            "overall_integrity_sha256": overall_hash,
            "data": datasets,
        }

        self._audit_logger.log_event(
            AuditEvent(
                actor="system",
                action="security.compliance.user_data_exported",
                resource_type="user",
                resource_id=user_id,
                outcome="success",
                metadata={"categories": list(datasets.keys()), "sha256": overall_hash},
            )
        )
        return archive

    def delete_user_data_compliance(
        self,
        user_id: str,
        deletion_handlers: list[Callable[[str], int]],
        requester: str = "user",
    ) -> int:
        """Executes Right-to-be-Forgotten deletion cascade after confirming no active legal hold exists."""
        if self.is_under_legal_hold("user", user_id):
            logger.error(
                "GDPR deletion blocked: User '%s' is under active legal hold", user_id
            )
            raise LegalHoldActiveError(
                f"Cannot delete user '{user_id}': active evidentiary legal hold in effect"
            )

        total_deleted = 0
        for handler in deletion_handlers:
            total_deleted += handler(user_id)

        self._audit_logger.log_event(
            AuditEvent(
                actor=requester,
                action="security.compliance.user_data_deleted",
                resource_type="user",
                resource_id=user_id,
                outcome="success",
                metadata={"deleted_count": total_deleted},
            )
        )
        return total_deleted
