import json
from pathlib import Path
from amberclaw.security.audit import SecurityAuditLogger, AuditEvent, redact_secrets


def test_audit_event_schema_defaults():
    event = AuditEvent(action="agent.task.execute", actor="user_123")
    assert event.action == "agent.task.execute"
    assert event.actor == "user_123"
    assert event.tenant == "default"
    assert event.outcome == "success"
    assert event.timestamp_utc != ""


def test_redact_secrets():
    raw_metadata = {
        "api_key": "sk-proj-1234567890abcdef",
        "nested": {
            "password": "supersecretpassword",
            "normal": "public_data",
        },
        "query": "Authorization: Bearer secret_bearer_token_xyz",
    }
    redacted = redact_secrets(raw_metadata)
    assert redacted["api_key"] == "[REDACTED_SECRET]"
    assert redacted["nested"]["password"] == "[REDACTED_SECRET]"
    assert redacted["nested"]["normal"] == "public_data"
    assert "[REDACTED_SECRET]" in redacted["query"]


def test_security_audit_logger_flow(tmp_path: Path):
    logger = SecurityAuditLogger(log_dir=tmp_path)

    event1 = logger.log_event(
        action="agent.create",
        actor="admin",
        resource_type="agent",
        resource_id="agent_007",
        metadata={"key": "val1"},
    )
    event2 = logger.log_event(
        action="tool.execute",
        actor="agent_007",
        resource_type="tool",
        resource_id="bash",
        metadata={"cmd": "ls -la", "api_key": "secret123456"},
    )

    log_file = tmp_path / "audit.jsonl"
    assert log_file.exists()

    lines = log_file.read_text().splitlines()
    assert len(lines) == 2

    entry1 = json.loads(lines[0])
    entry2 = json.loads(lines[1])

    assert entry1["index"] == 0
    assert entry2["index"] == 1
    assert entry2["previous_hash"] == entry1["hash"]
    assert entry2["metadata"]["api_key"] == "[REDACTED_SECRET]"

    # Integrity verification
    assert logger.verify_integrity() is True


def test_security_audit_logger_tamper_detection(tmp_path: Path):
    logger = SecurityAuditLogger(log_dir=tmp_path)
    logger.log_event(action="login", actor="user1")
    logger.log_event(action="transfer", actor="user1")

    log_file = tmp_path / "audit.jsonl"
    lines = log_file.read_text().splitlines()

    # Modify line 1 actor
    data = json.loads(lines[0])
    data["actor"] = "hacker"
    lines[0] = json.dumps(data)
    log_file.write_text("\n".join(lines) + "\n")

    assert logger.verify_integrity() is False
