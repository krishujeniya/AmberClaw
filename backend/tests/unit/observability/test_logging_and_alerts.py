# ruff: noqa: PLR2004
"""Unit tests for Structured Redacting JSON Logging, Safe Error Tracking, and SLO Monitoring."""

import hashlib
import json
import logging
from pathlib import Path

from amberclaw.observability.alerts import (
    AuditLogHealthChecker,
    SLOMonitor,
)
from amberclaw.observability.logging import (
    PrivacyPreservingErrorTracker,
    RedactingJsonLogFormatter,
)
from amberclaw.observability.tracing import Tracer


def test_redacting_json_log_formatter():
    formatter = RedactingJsonLogFormatter(service_name="test-os")
    tracer = Tracer(service_name="test-os")

    logger = logging.getLogger("test_redacting_logger")
    record = logger.makeRecord(
        name="test_logger",
        level=logging.ERROR,
        fn="test_fn.py",
        lno=42,
        msg="Leaked key: sk-ant-1234567890abcdef1234567890abcdef and DB postgres://admin:supersecret@10.0.0.1:5432/main",
        args=(),
        exc_info=None,
    )
    record.extra_user = "sk-" + "c" * 48  # Custom extra field with secret

    with tracer.start_as_current_span("span_turn") as span:
        output_json_str = formatter.format(record)
        data = json.loads(output_json_str)

        assert data["level"] == "ERROR"
        assert data["service"] == "test-os"
        assert data["trace_id"] == span.context.trace_id
        assert data["correlation_id"] == span.context.correlation_id

        # Secrets must be scrubbed from message and extra fields
        assert "sk-ant-1234567890abcdef" not in data["message"]
        assert "supersecret" not in data["message"]
        assert "[REDACTED]" in data["message"]
        assert "sk-" + "c" * 48 not in data["extra"]["extra_user"]
        assert "..." in data["extra"]["extra_user"]


def test_privacy_preserving_error_tracker():
    raw_error = ValueError(
        "Failed to connect to /home/ai/Documents/projects/secret/db.sqlite: "
        "invalid credential sk-" + "d" * 48
    )

    clean_summary = PrivacyPreservingErrorTracker.sanitize_error(
        raw_error,
        workspace_root="/home/ai/Documents/projects/secret",
    )

    assert clean_summary["error_type"] == "ValueError"
    assert clean_summary["sanitized"] is True
    # Path stripped
    assert "/home/ai/Documents/projects/secret" not in clean_summary["message"]
    # Secret stripped
    assert "sk-" + "d" * 48 not in clean_summary["message"]


def test_slo_monitor_breach_and_burn_rate():
    monitor = SLOMonitor(
        window_size=20, availability_target=0.95, p95_latency_target_ms=500.0
    )

    # 15 successful requests with fast latency
    for _ in range(15):
        monitor.record_request(success=True, latency_ms=100.0)

    assert monitor.current_availability == 1.0
    assert monitor.p95_latency_ms == 100.0
    assert len(monitor.evaluate_rules()) == 0

    # Inject 5 failures with 1200ms latency
    for _ in range(5):
        monitor.record_request(success=False, latency_ms=1200.0)

    # Availability is now 15/20 = 75%, breaching 95% target
    assert monitor.current_availability == 0.75
    assert monitor.p95_latency_ms == 1200.0
    assert monitor.error_budget_remaining == 0.0

    alerts = monitor.evaluate_rules()
    assert len(alerts) == 2
    rule_names = {a.rule_name for a in alerts}
    assert "AvailabilitySLOBreach" in rule_names
    assert "P95LatencySLOBreach" in rule_names


def test_audit_log_health_checker_valid_and_tampered(tmp_path: Path):
    audit_file = tmp_path / "audit.jsonl"

    # 1. Create a valid chained audit log
    def make_entry(prev_hash: str, action: str) -> dict:
        entry = {
            "timestamp": "2026-10-27T12:00:00Z",
            "action": action,
            "previous_hash": prev_hash,
        }
        canonical = json.dumps(entry, sort_keys=True).encode("utf-8")
        entry["hash"] = hashlib.sha256(canonical).hexdigest()
        return entry

    e1 = make_entry("GENESIS", "user.login")
    e2 = make_entry(e1["hash"], "tool.execute")
    e3 = make_entry(e2["hash"], "agent.exit")

    audit_file.write_text(
        json.dumps(e1) + "\n" + json.dumps(e2) + "\n" + json.dumps(e3) + "\n",
        encoding="utf-8",
    )

    valid_report = AuditLogHealthChecker.verify_log_file(audit_file)
    assert valid_report.healthy is True
    assert valid_report.total_events == 3
    assert valid_report.broken_chain_index is None

    # 2. Tamper with second entry content without recalculating hash
    e2_tampered = dict(e2)
    e2_tampered["action"] = "tool.execute.MALICIOUS"
    audit_file.write_text(
        json.dumps(e1) + "\n" + json.dumps(e2_tampered) + "\n" + json.dumps(e3) + "\n",
        encoding="utf-8",
    )

    tampered_report = AuditLogHealthChecker.verify_log_file(audit_file)
    assert tampered_report.healthy is False
    assert tampered_report.broken_chain_index == 1
    assert "Tamper detected" in tampered_report.error
