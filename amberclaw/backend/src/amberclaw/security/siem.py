# ruff: noqa: A002, PLC0415, PTH123, PLW2901
"""SIEM Log Exporter and Audit Log Retention Lifecycle Manager.

Implements:
1. SIEM event formatting supporting RFC 5424 Syslog, ArcSight CEF, and JSON-NDJSON.
2. Webhook forwarder for Splunk HEC, Datadog, and Elastic Logstash HTTP inputs.
3. Cryptographically sound retention pruning: verifies chain integrity before archiving and pruning.
"""

import gzip
import json
import socket
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from amberclaw.security.audit import AuditEvent, SecurityAuditLogger


class SIEMFormat(StrEnum):
    """Supported SIEM ingestion formats."""

    RFC5424_SYSLOG = "rfc5424"
    CEF = "cef"
    JSON_NDJSON = "json_ndjson"


class SIEMExporter:
    """Formats and exports AmberClaw audit events to external SIEM systems."""

    FACILITY_LOCAL0 = 16
    SEVERITY_INFORMATIONAL = 6
    SEVERITY_WARNING = 4
    SEVERITY_ALERT = 1

    @classmethod
    def _get_pri(cls, outcome: str) -> int:
        """Compute Syslog PRI value based on event outcome."""
        sev = cls.SEVERITY_INFORMATIONAL
        if outcome in ("denied", "failure", "compromised"):
            sev = cls.SEVERITY_WARNING
        elif outcome in ("blocked", "emergency"):
            sev = cls.SEVERITY_ALERT
        return (cls.FACILITY_LOCAL0 * 8) + sev

    @classmethod
    def format_syslog_rfc5424(
        cls, event: AuditEvent, app_name: str = "AmberClaw"
    ) -> str:
        """Format an AuditEvent according to the IETF RFC 5424 Syslog protocol standard."""
        pri = cls._get_pri(event.outcome)
        hostname = socket.gethostname() or "localhost"
        timestamp = event.timestamp_utc or datetime.now(UTC).isoformat()
        msg_id = event.correlation_id or "-"

        # Structured Data Element
        meta_pairs = " ".join(
            f'{k}="{v}"'
            for k, v in (event.metadata or {}).items()
            if isinstance(v, (str, int, float, bool))
        )
        sd_element = (
            f'[amberclaw@60416 action="{event.action}" actor="{event.actor}" '
            f'tenant="{event.tenant}" outcome="{event.outcome}" '
            f'resource="{event.resource_type}:{event.resource_id}"'
            f"{' ' + meta_pairs if meta_pairs else ''}]"
        )

        msg = f"Audit action {event.action} by {event.actor} outcome={event.outcome}"
        return (
            f"<{pri}>1 {timestamp} {hostname} {app_name} - {msg_id} {sd_element} {msg}"
        )

    @classmethod
    def format_cef(cls, event: AuditEvent) -> str:
        """Format an AuditEvent according to ArcSight Common Event Format (CEF)."""
        severity = 3
        if event.outcome in ("denied", "failure"):
            severity = 7
        elif event.outcome in ("blocked", "compromised"):
            severity = 10

        extensions = [
            f"suser={event.actor}",
            f"act={event.action}",
            f"outcome={event.outcome}",
            f"cs1={event.resource_type}",
            "cs1Label=ResourceType",
            f"cs2={event.resource_id}",
            "cs2Label=ResourceID",
            f"cs3={event.tenant}",
            "cs3Label=Tenant",
        ]
        if event.correlation_id:
            extensions.append(f"externalId={event.correlation_id}")

        ext_str = " ".join(extensions)
        return f"CEF:0|AmberClaw|AI_OS|2026.0.1|{event.action}|{event.action}|{severity}|{ext_str}"

    @classmethod
    def export_events(
        cls, events: list[AuditEvent], format: SIEMFormat = SIEMFormat.JSON_NDJSON
    ) -> str:
        """Export multiple audit events into the designated SIEM format string."""
        lines = []
        for e in events:
            if format == SIEMFormat.RFC5424_SYSLOG:
                lines.append(cls.format_syslog_rfc5424(e))
            elif format == SIEMFormat.CEF:
                lines.append(cls.format_cef(e))
            else:
                lines.append(json.dumps(e.model_dump()))
        return "\n".join(lines)

    @classmethod
    async def forward_to_webhook(
        cls,
        events: list[AuditEvent],
        webhook_url: str,
        format: SIEMFormat = SIEMFormat.JSON_NDJSON,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> bool:
        """Forward batch of audit events to an HTTP SIEM receiver (Splunk, Elastic, Datadog)."""
        payload = cls.export_events(events, format=format)
        req_headers = {
            "Content-Type": "application/json"
            if format == SIEMFormat.JSON_NDJSON
            else "text/plain"
        }
        if headers:
            req_headers.update(headers)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    webhook_url, content=payload, headers=req_headers
                )
                return resp.status_code in (200, 201, 202)
        except Exception as e:
            logger.error(
                "Failed to forward {} audit events to SIEM at {}: {}",
                len(events),
                webhook_url,
                e,
            )
            return False


class AuditRetentionManager:
    """Manages audit log retention policies, archiving, and integrity-preserving log rotation."""

    @classmethod
    def prune_and_archive(
        cls,
        log_file: Path | str,
        retention_days: int = 90,
        archive_dir: Path | str | None = None,
    ) -> dict[str, Any]:
        """Verify chain integrity, archive logs older than retention_days, and rewrite active log."""
        path = Path(log_file)
        if not path.exists():
            return {"archived": 0, "retained": 0, "status": "no_file"}

        # 1. Verify tamper integrity prior to any archival or pruning
        auditor = SecurityAuditLogger()
        if not auditor.verify_integrity(target_file=path):
            raise ValueError(
                f"Tamper detection check failed for '{path}'. Pruning aborted to preserve digital forensics."
            )

        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        retained_records: list[dict[str, Any]] = []
        archived_records: list[dict[str, Any]] = []

        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                ts_str = record.get("timestamp_utc", record.get("timestamp"))
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except Exception:
                    ts = datetime.now(UTC)

                if ts < cutoff:
                    archived_records.append(record)
                else:
                    retained_records.append(record)

        # 2. Archive older records if any exist
        archived_file: Path | None = None
        if archived_records:
            arch_base = Path(archive_dir) if archive_dir else path.parent / "archives"
            arch_base.mkdir(parents=True, exist_ok=True)
            today_str = datetime.now(UTC).strftime("%Y%m%d")
            archived_file = arch_base / f"audit_archive_{today_str}.jsonl.gz"

            with gzip.open(archived_file, "wt", encoding="utf-8") as gz_f:
                for r in archived_records:
                    gz_f.write(json.dumps(r) + "\n")

        # 3. Rewrite active log with re-chained integrity proofs for retained records
        with open(path, "w", encoding="utf-8") as f:
            prev_hash = "0" * 64
            for idx, r in enumerate(retained_records):
                r["index"] = idx
                r["previous_hash"] = prev_hash
                ts = r.get("timestamp_utc", "")
                actor = r.get("actor", "")
                action = r.get("action", "")
                details = json.dumps(
                    {
                        "tenant": r.get("tenant", "default"),
                        "resource_type": r.get("resource_type", "unknown"),
                        "resource_id": r.get("resource_id", "unknown"),
                        "outcome": r.get("outcome", "success"),
                        "correlation_id": r.get("correlation_id", ""),
                        "metadata": r.get("metadata", {}),
                    },
                    sort_keys=True,
                )
                payload_str = f"{idx}|{ts}|{actor}|{action}|{details}|{prev_hash}"
                import hashlib

                proof = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
                r["integrity_proof"] = proof
                r["hash"] = proof
                prev_hash = proof
                f.write(json.dumps(r) + "\n")

        logger.info(
            "Audit log retention pruned: {} records archived to {}, {} records retained.",
            len(archived_records),
            archived_file,
            len(retained_records),
        )

        return {
            "archived_count": len(archived_records),
            "retained_count": len(retained_records),
            "archive_path": str(archived_file) if archived_file else None,
            "status": "success",
        }
