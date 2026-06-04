"""AmberClaw Governance: Cryptographically Verifiable Audit System.

Ensures agent action logs are tamper-evident via SHA-256 hash chaining.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from loguru import logger


class AuditLogger:
    """Logs all agent actions for compliance and forensics with tamper-evidence."""

    def __init__(self, log_dir: str = "data/audit"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _calculate_hash(
        self,
        index: int,
        timestamp: str,
        agent_id: str,
        action: str,
        details: dict[str, Any],
        previous_hash: str,
    ) -> str:
        """Calculate SHA-256 hash for a log entry deterministically."""
        details_str = json.dumps(details, sort_keys=True)
        payload = f"{index}|{timestamp}|{agent_id}|{action}|{details_str}|{previous_hash}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _get_last_entry(self, log_file: Path) -> tuple[int, str]:
        """Read the last line of the log file to get the last index and hash."""
        if not log_file.exists() or log_file.stat().st_size == 0:
            return -1, "0" * 64

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                # Seek to end of file, read last chunk
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - 4096))
                lines = f.readlines()
                if lines:
                    last_line = lines[-1].strip()
                    if last_line:
                        data = json.loads(last_line)
                        return data.get("index", 0), data.get("hash", "0" * 64)
        except Exception as e:
            logger.error("Failed to read last entry from log: {}", e)

        return -1, "0" * 64

    def log_action(
        self, agent_id: str, action: str, details: dict[str, Any]
    ) -> str:
        """Log an agent action, appending to the cryptographic hash chain."""
        timestamp = datetime.now(timezone.utc).isoformat()
        log_file = (
            self.log_dir / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
        )

        last_index, previous_hash = self._get_last_entry(log_file)
        next_index = last_index + 1

        entry_hash = self._calculate_hash(
            next_index, timestamp, agent_id, action, details, previous_hash
        )

        log_entry = {
            "index": next_index,
            "timestamp": timestamp,
            "agent_id": agent_id,
            "action": action,
            "details": details,
            "previous_hash": previous_hash,
            "hash": entry_hash,
        }

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")

        logger.debug(
            "Verifiable audit log entry created for {}: {} (index={})",
            agent_id,
            action,
            next_index,
        )
        return entry_hash

    def verify_chain(self, log_file: Path) -> bool:
        """Verify the cryptographic integrity of the audit log file."""
        if not log_file.exists():
            return True

        try:
            expected_prev_hash = "0" * 64
            expected_index = 0

            with open(log_file, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    data = json.loads(line)

                    # 1. Check index
                    idx = data.get("index")
                    if idx != expected_index:
                        logger.error(
                            "Verification failed at line {}: expected index {}, got {}",
                            line_num,
                            expected_index,
                            idx,
                        )
                        return False

                    # 2. Check previous hash link
                    prev_hash = data.get("previous_hash")
                    if prev_hash != expected_prev_hash:
                        logger.error(
                            "Verification failed at line {}: expected previous_hash {}, got {}",
                            line_num,
                            expected_prev_hash,
                            prev_hash,
                        )
                        return False

                    # 3. Recalculate and verify hash
                    timestamp = data.get("timestamp", "")
                    agent_id = data.get("agent_id", "")
                    action = data.get("action", "")
                    details = data.get("details", {})
                    current_hash = data.get("hash")

                    recalculated = self._calculate_hash(
                        idx, timestamp, agent_id, action, details, prev_hash
                    )
                    if current_hash != recalculated:
                        logger.error(
                            "Verification failed at line {}: hash mismatch", line_num
                        )
                        return False

                    expected_prev_hash = current_hash
                    expected_index += 1

            return True
        except Exception as e:
            logger.error("Error verifying audit log chain: {}", e)
            return False


# Global audit logger
auditor = AuditLogger()
