import hashlib
import json
import threading
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


class AuditAction(StrEnum):
    AGENT_DECISION = "agent_decision"
    TOOL_EXECUTION = "tool_execution"
    GOVERNANCE_APPROVAL = "governance_approval"
    GOVERNANCE_REJECTION = "governance_rejection"
    POLICY_VIOLATION = "policy_violation"
    SYSTEM_ALERT = "system_alert"


class AuditRecord(BaseModel):
    index: int
    timestamp: str
    action: str
    actor_id: str
    target_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    previous_hash: str
    hash: str

    @property
    def prev_hash(self) -> str:
        return self.previous_hash

    @property
    def record_hash(self) -> str:
        return self.hash


class AuditQuery(BaseModel):
    action: AuditAction | None = None
    actor_id: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    limit: int = 100


class AuditLogger:
    """An immutable, append-only tamper-evident audit logger."""

    def __init__(self, log_dir: str | Path = "logs/audit") -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _calculate_hash(
        self,
        entry_data: dict[str, Any],
    ) -> str:
        data = f"{entry_data['index']}|{entry_data['timestamp']}|{entry_data['action']}|{entry_data['actor_id']}|{entry_data.get('target_id')}|{json.dumps(entry_data['details'], sort_keys=True)}|{entry_data['previous_hash']}"
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def _get_log_file_for_date(self, date_str: str) -> Path:
        return self.log_dir / f"{date_str}.jsonl"

    def _get_last_record(self, log_file: Path) -> AuditRecord | None:
        if not log_file.exists():
            return None

        try:
            with log_file.open(encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
                if lines:
                    return AuditRecord.model_validate_json(lines[-1])
        except Exception:
            return None
        return None

    def log_action(
        self,
        actor_id: str,
        action: str,
        details: dict[str, Any] | None = None,
        target_id: str | None = None,
    ) -> AuditRecord:
        """Appends a new audit record to the daily audit log in a tamper-evident manner."""
        with self._lock:
            now = datetime.now(UTC)
            date_str = now.strftime("%Y-%m-%d")
            timestamp = now.isoformat()

            log_file = self._get_log_file_for_date(date_str)
            last_record = self._get_last_record(log_file)

            index = (last_record.index + 1) if last_record else 0
            previous_hash = (
                last_record.hash
                if last_record
                else "0000000000000000000000000000000000000000000000000000000000000000"
            )

            record_details = details or {}
            entry_data = {
                "index": index,
                "timestamp": timestamp,
                "action": action,
                "actor_id": actor_id,
                "target_id": target_id,
                "details": record_details,
                "previous_hash": previous_hash,
            }
            record_hash = self._calculate_hash(entry_data)

            log_entry = {
                **entry_data,
                "hash": record_hash,
            }

            with log_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")

            return AuditRecord.model_validate(log_entry)

    def log(
        self,
        action: AuditAction | str,
        actor_id: str,
        target_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditRecord:
        """Alias for log_action."""
        act_str = action.value if isinstance(action, AuditAction) else str(action)
        return self.log_action(
            actor_id=actor_id,
            action=act_str,
            details=details,
            target_id=target_id,
        )

    def verify_chain(self, log_file: Path | str) -> bool:
        """Verifies the hash chain integrity for a specific log file."""
        file_path = Path(log_file)
        if not file_path.exists():
            return True

        expected_previous_hash = (
            "0000000000000000000000000000000000000000000000000000000000000000"
        )
        expected_index = 0

        with file_path.open(encoding="utf-8") as f:
            for line_raw in f:
                line_str = line_raw.strip()
                if not line_str:
                    continue

                try:
                    entry = json.loads(line_str)
                except json.JSONDecodeError:
                    return False

                if entry.get("index") != expected_index:
                    return False

                if entry.get("previous_hash") != expected_previous_hash:
                    return False

                entry_data = {
                    "index": entry.get("index", 0),
                    "timestamp": entry.get("timestamp", ""),
                    "actor_id": entry.get("actor_id", ""),
                    "action": entry.get("action", ""),
                    "target_id": entry.get("target_id"),
                    "details": entry.get("details", {}),
                    "previous_hash": entry.get("previous_hash", ""),
                }
                calculated_hash = self._calculate_hash(entry_data)

                if entry.get("hash") != calculated_hash:
                    return False

                expected_previous_hash = calculated_hash
                expected_index += 1

        return True

    def verify_integrity(self, date_str: str | None = None) -> bool:
        """Verify chain integrity for a given date or today."""
        d_str = date_str or datetime.now(UTC).strftime("%Y-%m-%d")
        return self.verify_chain(self._get_log_file_for_date(d_str))

    def query(self, query: AuditQuery) -> list[AuditRecord]:
        """Query audit log records matching criteria across log files."""
        records: list[AuditRecord] = []
        log_files = sorted(self.log_dir.glob("*.jsonl"), reverse=True)
        for log_file in log_files:
            with log_file.open(encoding="utf-8") as f:
                for line in f:
                    line_str = line.strip()
                    if not line_str:
                        continue
                    try:
                        record = AuditRecord.model_validate_json(line_str)
                        if query.action and record.action != query.action:
                            continue
                        if query.actor_id and record.actor_id != query.actor_id:
                            continue
                        if query.start_time and record.timestamp < query.start_time:
                            continue
                        if query.end_time and record.timestamp > query.end_time:
                            continue
                        records.append(record)
                        if len(records) >= query.limit:
                            return records
                    except Exception as e:
                        logger.debug("Failed to parse audit record line: {}", e)
                        continue
        return records


audit_logger = AuditLogger()
