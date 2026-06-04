import json
from pathlib import Path
from datetime import datetime, timezone
from amberclaw.governance.audit import AuditLogger


def test_audit_log_verification_happy_path(tmp_path: Path) -> None:
    """Test that a sequence of log actions generates a valid and verifiable hash chain."""
    logger = AuditLogger(log_dir=str(tmp_path))
    
    # Log multiple actions
    logger.log_action("agent-1", "start", {"param": "val1"})
    logger.log_action("agent-1", "query", {"param": "val2"})
    logger.log_action("agent-2", "stop", {"param": "val3"})

    log_file = tmp_path / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
    assert log_file.exists()

    # Verify chain
    assert logger.verify_chain(log_file) is True


def test_audit_log_tamper_detection_field_modified(tmp_path: Path) -> None:
    """Test that modifying a field in an entry breaks the chain validation."""
    logger = AuditLogger(log_dir=str(tmp_path))
    
    logger.log_action("agent-1", "start", {"param": "val1"})
    logger.log_action("agent-1", "query", {"param": "val2"})
    logger.log_action("agent-2", "stop", {"param": "val3"})

    log_file = tmp_path / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
    
    # Read lines
    lines = log_file.read_text().splitlines()
    assert len(lines) == 3

    # Tamper with the middle entry (index 1)
    data = json.loads(lines[1])
    data["details"]["param"] = "tampered_value"
    lines[1] = json.dumps(data)
    log_file.write_text("\n".join(lines) + "\n")

    # Verify chain detects the tamper
    assert logger.verify_chain(log_file) is False


def test_audit_log_tamper_detection_deleted_line(tmp_path: Path) -> None:
    """Test that deleting a log entry breaks the index and hash chaining validation."""
    logger = AuditLogger(log_dir=str(tmp_path))
    
    logger.log_action("agent-1", "start", {"param": "val1"})
    logger.log_action("agent-1", "query", {"param": "val2"})
    logger.log_action("agent-2", "stop", {"param": "val3"})

    log_file = tmp_path / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
    
    # Read lines and delete the middle one
    lines = log_file.read_text().splitlines()
    assert len(lines) == 3
    del lines[1]
    log_file.write_text("\n".join(lines) + "\n")

    # Verify chain detects the missing link
    assert logger.verify_chain(log_file) is False


def test_audit_log_chain_continuation(tmp_path: Path) -> None:
    """Test that initializing a new logger instance continues chaining from the existing log file."""
    logger_one = AuditLogger(log_dir=str(tmp_path))
    logger_one.log_action("agent-1", "step-1", {})
    
    log_file = tmp_path / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"

    # Initialize a second logger pointing to the same folder
    logger_two = AuditLogger(log_dir=str(tmp_path))
    logger_two.log_action("agent-1", "step-2", {})

    # Ensure index increments and chain remains intact
    lines = log_file.read_text().splitlines()
    assert len(lines) == 2
    
    entry_one = json.loads(lines[0])
    entry_two = json.loads(lines[1])

    assert entry_one["index"] == 0
    assert entry_two["index"] == 1
    assert entry_two["previous_hash"] == entry_one["hash"]

    assert logger_two.verify_chain(log_file) is True
