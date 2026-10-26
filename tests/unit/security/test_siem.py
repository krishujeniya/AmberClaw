# ruff: noqa: PLC0415, PLR2004
"""Unit tests for SIEM Log Export and Audit Retention Lifecycle Management.

Validates:
1. RFC 5424 standard Syslog format serialization with structured data elements
2. ArcSight Common Event Format (CEF) formatting and severity mapping
3. HTTP SIEM webhook batch forwarding
4. Tamper verification gating prior to log pruning
5. Audit log archiving to compressed .jsonl.gz
6. Retention pruning and cryptographic re-chaining of active logs
"""

import gzip
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from amberclaw.security.audit import AuditEvent, SecurityAuditLogger
from amberclaw.security.siem import (
    AuditRetentionManager,
    SIEMExporter,
    SIEMFormat,
)


def test_rfc5424_syslog_formatting():
    event = AuditEvent(
        actor="dev_user",
        action="tool.execute",
        resource_type="shell",
        resource_id="bash",
        outcome="success",
        correlation_id="corr_123",
        metadata={"command": "ls -la", "exit_code": 0},
    )

    syslog_msg = SIEMExporter.format_syslog_rfc5424(event, app_name="AmberClawCore")
    assert syslog_msg.startswith("<134>1 ")  # Facility local0 (16*8) + Info (6) = 134
    assert "AmberClawCore" in syslog_msg
    assert "corr_123" in syslog_msg
    assert 'action="tool.execute"' in syslog_msg
    assert 'actor="dev_user"' in syslog_msg
    assert 'outcome="success"' in syslog_msg


def test_cef_formatting():
    event_blocked = AuditEvent(
        actor="attacker",
        action="security.prompt_injection",
        resource_type="prompt",
        resource_id="web_search",
        outcome="blocked",
        correlation_id="cid_999",
        metadata={"score": 0.95},
    )

    cef_msg = SIEMExporter.format_cef(event_blocked)
    assert cef_msg.startswith(
        "CEF:0|AmberClaw|AI_OS|2026.0.1|security.prompt_injection|security.prompt_injection|10|"
    )
    assert "suser=attacker" in cef_msg
    assert "outcome=blocked" in cef_msg
    assert "cs1=prompt" in cef_msg
    assert "externalId=cid_999" in cef_msg


@pytest.mark.asyncio
async def test_siem_forward_to_webhook():
    events = [
        AuditEvent(actor="admin", action="login", outcome="success"),
        AuditEvent(actor="operator", action="vault.secret_accessed", outcome="success"),
    ]

    mock_resp = httpx.Response(200, json={"status": "ingested"})
    with patch("httpx.AsyncClient.post", return_value=mock_resp) as mock_post:
        success = await SIEMExporter.forward_to_webhook(
            events,
            webhook_url="https://siem.internal/v1/logs",
            format=SIEMFormat.JSON_NDJSON,
        )
        assert success is True
        mock_post.assert_awaited_once()


def test_audit_retention_prune_and_archive(tmp_path: Path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "audit.jsonl"

    logger_inst = SecurityAuditLogger(log_dir=log_dir)

    # Log 3 events
    logger_inst.log_event(action="event_1", actor="u1")
    logger_inst.log_event(action="event_2", actor="u2")
    logger_inst.log_event(action="event_3", actor="u3")

    # Tamper one event line timestamp to make it 100 days old
    old_time = (datetime.now(UTC) - timedelta(days=100)).isoformat()
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    data_0 = json.loads(lines[0])
    data_0["timestamp_utc"] = old_time
    # Recalculate hash for data_0 so the chain remains valid
    payload_str = f"0|{old_time}|{data_0['actor']}|{data_0['action']}|{json.dumps({'tenant': 'default', 'resource_type': 'unknown', 'resource_id': 'unknown', 'outcome': 'success', 'correlation_id': '', 'metadata': {}}, sort_keys=True)}|{'0' * 64}"
    import hashlib

    new_h = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    data_0["integrity_proof"] = new_h
    data_0["hash"] = new_h

    # Re-chain line 1 and 2
    data_1 = json.loads(lines[1])
    data_1["previous_hash"] = new_h
    payload_1 = f"1|{data_1['timestamp_utc']}|{data_1['actor']}|{data_1['action']}|{json.dumps({'tenant': 'default', 'resource_type': 'unknown', 'resource_id': 'unknown', 'outcome': 'success', 'correlation_id': '', 'metadata': {}}, sort_keys=True)}|{new_h}"
    new_h1 = hashlib.sha256(payload_1.encode("utf-8")).hexdigest()
    data_1["integrity_proof"] = new_h1
    data_1["hash"] = new_h1

    data_2 = json.loads(lines[2])
    data_2["previous_hash"] = new_h1
    payload_2 = f"2|{data_2['timestamp_utc']}|{data_2['actor']}|{data_2['action']}|{json.dumps({'tenant': 'default', 'resource_type': 'unknown', 'resource_id': 'unknown', 'outcome': 'success', 'correlation_id': '', 'metadata': {}}, sort_keys=True)}|{new_h1}"
    new_h2 = hashlib.sha256(payload_2.encode("utf-8")).hexdigest()
    data_2["integrity_proof"] = new_h2
    data_2["hash"] = new_h2

    log_file.write_text(
        f"{json.dumps(data_0)}\n{json.dumps(data_1)}\n{json.dumps(data_2)}\n",
        encoding="utf-8",
    )

    # Prune logs older than 90 days
    result = AuditRetentionManager.prune_and_archive(
        log_file=log_file,
        retention_days=90,
        archive_dir=log_dir / "archives",
    )

    assert result["status"] == "success"
    assert result["archived_count"] == 1
    assert result["retained_count"] == 2
    assert Path(result["archive_path"]).exists()

    # Verify archived .jsonl.gz contains data_0
    with gzip.open(result["archive_path"], "rt", encoding="utf-8") as gz:
        archived_line = gz.readline()
        assert "event_1" in archived_line

    # Verify pruned active log has valid hash chain
    assert logger_inst.verify_integrity(target_file=log_file) is True
