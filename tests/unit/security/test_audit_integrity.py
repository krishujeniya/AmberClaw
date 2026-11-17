"""Security audit concurrency, truncation detection, and receipt verification tests (CL-007 / A07)."""

import concurrent.futures
import json
from pathlib import Path

import pytest

from amberclaw.security.audit import AuditEvent, SecurityAuditLogger


def test_concurrent_logging_preserves_linear_chain_without_forks(tmp_path):
    log_dir = tmp_path / "concurrent_audit"
    logger = SecurityAuditLogger(log_dir=log_dir)

    num_threads = 8
    events_per_thread = 10
    total_events = num_threads * events_per_thread

    def worker(worker_id: int):
        thread_logger = SecurityAuditLogger(log_dir=log_dir)
        for i in range(events_per_thread):
            thread_logger.log_event(
                action=f"worker.action.{worker_id}",
                actor=f"worker_{worker_id}",
                metadata={"seq": i},
            )

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, w_id) for w_id in range(num_threads)]
        concurrent.futures.wait(futures)

    # 1. Total written events must equal total expected
    lines = [line.strip() for line in (log_dir / "audit.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == total_events

    # 2. Indices must be strictly contiguous from 0 to total_events - 1
    indices = [json.loads(line)["index"] for line in lines]
    assert indices == list(range(total_events))

    # 3. Cryptographic chain must verify cleanly
    assert logger.verify_integrity() is True


def test_audit_integrity_detects_payload_modification(tmp_path):
    log_dir = tmp_path / "tamper_edit"
    logger = SecurityAuditLogger(log_dir=log_dir)

    logger.log_event(action="step.1", actor="alice")
    logger.log_event(action="step.2", actor="bob")
    logger.log_event(action="step.3", actor="charlie")

    assert logger.verify_integrity() is True

    # Tamper with record 1
    audit_file = log_dir / "audit.jsonl"
    lines = audit_file.read_text(encoding="utf-8").splitlines()
    data = json.loads(lines[1])
    data["actor"] = "mallory"  # Modify actor
    lines[1] = json.dumps(data)
    audit_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert logger.verify_integrity() is False


def test_audit_integrity_detects_record_deletion(tmp_path):
    log_dir = tmp_path / "tamper_delete"
    logger = SecurityAuditLogger(log_dir=log_dir)

    for i in range(5):
        logger.log_event(action=f"step.{i}", actor="alice")

    assert logger.verify_integrity() is True

    # Delete middle record (index 2)
    audit_file = log_dir / "audit.jsonl"
    lines = audit_file.read_text(encoding="utf-8").splitlines()
    del lines[2]
    audit_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert logger.verify_integrity() is False


def test_audit_integrity_detects_record_reordering(tmp_path):
    log_dir = tmp_path / "tamper_reorder"
    logger = SecurityAuditLogger(log_dir=log_dir)

    for i in range(4):
        logger.log_event(action=f"step.{i}", actor="alice")

    assert logger.verify_integrity() is True

    # Swap record 1 and record 2
    audit_file = log_dir / "audit.jsonl"
    lines = audit_file.read_text(encoding="utf-8").splitlines()
    lines[1], lines[2] = lines[2], lines[1]
    audit_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert logger.verify_integrity() is False


def test_anchor_receipt_detects_tail_truncation(tmp_path):
    log_dir = tmp_path / "tamper_truncation"
    logger = SecurityAuditLogger(log_dir=log_dir)

    for i in range(10):
        logger.log_event(action=f"operation.{i}", actor="operator")

    anchor = logger.create_anchor_receipt()
    assert anchor.anchor_index == 9
    assert anchor.record_count == 10

    # Verification against anchor passes on intact log
    assert logger.verify_integrity(expected_anchor=anchor) is True

    # Attacker truncates the log by dropping the last 3 records
    audit_file = log_dir / "audit.jsonl"
    lines = audit_file.read_text(encoding="utf-8").splitlines()
    truncated_lines = lines[:7]
    audit_file.write_text("\n".join(truncated_lines) + "\n", encoding="utf-8")

    # Plain verification without anchor passes because prefix is self-consistent
    assert logger.verify_integrity() is True

    # Anchored verification catches truncation failure
    assert logger.verify_integrity(expected_anchor=anchor) is False


def test_export_event_receipt_and_verification(tmp_path):
    log_dir = tmp_path / "receipts"
    logger = SecurityAuditLogger(log_dir=log_dir)

    canary_key = "sk-live-canary-secret-token-key-998877"
    event = logger.log_event(
        action="model.invoke",
        actor="lead_analyst",
        tenant="tenant_omega",
        resource_type="model_endpoint",
        resource_id="claude-3-5-sonnet",
        metadata={"api_key": canary_key, "query": "summarize quarterly numbers"},
    )

    receipt = logger.export_event_receipt(event)
    assert receipt["actor"] == "lead_analyst"
    assert receipt["action"] == "model.invoke"
    assert receipt["integrity_proof"] == event.integrity_proof
    # Sensitive credentials scrubbed
    assert canary_key not in json.dumps(receipt)
    assert receipt["metadata"]["api_key"] == "[REDACTED_SECRET]"

    # Verify receipt against log
    assert logger.verify_receipt(receipt) is True

    # Tampered receipt proof fails
    fake_receipt = dict(receipt)
    fake_receipt["integrity_proof"] = "0" * 64
    assert logger.verify_receipt(fake_receipt) is False
