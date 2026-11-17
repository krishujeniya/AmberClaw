# ruff: noqa: PLR2004
"""Unit tests for CL-014: Explain Every Run, Correlation, and Redaction."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest

from amberclaw.observability.run_tracer import (
    RunReplayFixture,
    RunReconstructor,
    RunTimelineEvent,
    RunTraceContext,
    TraceRedactionPolicy,
    bound_run_context,
    get_current_run_context,
)
from amberclaw.observability.tracing import SpanStatusCode, Tracer
from amberclaw.runtime.durable import DurableRun, DurableStep, RunStatus, StepStatus


def test_run_context_ambient_propagation_and_isolation():
    """Verify ambient context binds, nests, and isolates across execution scopes."""
    assert get_current_run_context() is None

    with bound_run_context(run_id="run_alpha", tenant_id="tenant_finance", step_index=0) as ctx1:
        assert ctx1.run_id == "run_alpha"
        assert ctx1.tenant_id == "tenant_finance"
        assert ctx1.step_index == 0
        assert len(ctx1.trace_id) == 32

        # Nested step inherits run_id and trace_id but updates step_index
        with bound_run_context(run_id="run_alpha", tenant_id="tenant_finance", step_index=1, step_id="st_1") as ctx2:
            assert ctx2.run_id == "run_alpha"
            assert ctx2.tenant_id == "tenant_finance"
            assert ctx2.step_index == 1
            assert ctx2.step_id == "st_1"
            assert ctx2.trace_id == ctx1.trace_id

        # Returned to parent step context
        curr = get_current_run_context()
        assert curr is not None
        assert curr.step_index == 0

    assert get_current_run_context() is None


@pytest.mark.asyncio
async def test_run_context_async_concurrency_isolation():
    """Verify concurrent async coroutines maintain distinct run correlation contexts."""
    async def worker(run_id: str, tenant_id: str, step_index: int) -> dict[str, Any]:
        with bound_run_context(run_id=run_id, tenant_id=tenant_id, step_index=step_index) as ctx:
            await asyncio.sleep(0.01)
            active = get_current_run_context()
            assert active is not None
            return {
                "run_id": active.run_id,
                "tenant_id": active.tenant_id,
                "step_index": active.step_index,
                "trace_id": active.trace_id,
            }

    results = await asyncio.gather(
        worker("run_1", "tenant_a", 10),
        worker("run_2", "tenant_b", 20),
        worker("run_3", "tenant_c", 30),
    )

    assert results[0]["run_id"] == "run_1"
    assert results[0]["tenant_id"] == "tenant_a"
    assert results[0]["step_index"] == 10

    assert results[1]["run_id"] == "run_2"
    assert results[1]["tenant_id"] == "tenant_b"
    assert results[1]["step_index"] == 20

    assert results[2]["run_id"] == "run_3"
    assert results[2]["tenant_id"] == "tenant_c"
    assert results[2]["step_index"] == 30

    # Ensure all trace_ids are unique
    trace_ids = [r["trace_id"] for r in results]
    assert len(set(trace_ids)) == 3


def test_reconstruct_failed_run_timeline_and_correlation():
    """Verify a multi-step run with approval, retry, failure, and compensation is fully reconstructed."""
    t0 = datetime(2026, 11, 9, 8, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 11, 9, 8, 1, 0, tzinfo=UTC)
    t2 = datetime(2026, 11, 9, 8, 2, 0, tzinfo=UTC)
    t3 = datetime(2026, 11, 9, 8, 3, 0, tzinfo=UTC)

    step0 = DurableStep(
        step_id="st_0",
        run_id="run_order_99",
        step_index=0,
        action_type="fetch_order",
        tool_name="database_query",
        idempotency_key="ik_0",
        status=StepStatus.COMPLETED,
        args={"order_id": 1234},
        result={"status": "pending_charge", "amount": 250},
        created_at=t0,
        updated_at=t0,
    )

    step1 = DurableStep(
        step_id="st_1",
        run_id="run_order_99",
        step_index=1,
        action_type="charge_card",
        tool_name="stripe_payment",
        idempotency_key="ik_1",
        status=StepStatus.COMPLETED,
        args={"amount": 250, "token": "tok_visa_valid"},
        result={"charge_id": "ch_789"},
        approval_ticket_id="ticket_appr_01",
        is_side_effect=True,
        compensation_action="refund_charge",
        compensation_args={"charge_id": "ch_789"},
        created_at=t1,
        updated_at=t1,
    )

    step2 = DurableStep(
        step_id="st_2",
        run_id="run_order_99",
        step_index=2,
        action_type="generate_shipping_label",
        tool_name="fedex_api",
        idempotency_key="ik_2",
        status=StepStatus.FAILED,
        args={"destination": "Seattle, WA"},
        error="Connection reset by peer at FedEx API endpoint",
        created_at=t2,
        updated_at=t2,
    )

    step3 = DurableStep(
        step_id="st_3",
        run_id="run_order_99",
        step_index=3,
        action_type="refund_charge",
        tool_name="stripe_refund",
        idempotency_key="ik_3",
        status=StepStatus.COMPENSATED,
        args={"charge_id": "ch_789"},
        result={"refund_id": "ref_456"},
        created_at=t3,
        updated_at=t3,
    )

    durable_run = DurableRun(
        run_id="run_order_99",
        tenant_id="tenant_ecommerce",
        workflow_name="process_order_workflow",
        status=RunStatus.FAILED,
        initial_input={"order_id": 1234},
        current_step_index=2,
        steps=[step0, step1, step2, step3],
        created_at=t0,
        updated_at=t3,
    )

    retries = [
        {
            "step_index": 2,
            "attempt": 1,
            "timestamp": t2,
            "error": "HTTP 503 Service Unavailable",
            "backoff_s": 1.0,
        }
    ]

    reconstructor = RunReconstructor()
    fixture = reconstructor.reconstruct_from_durable_run(durable_run, retries=retries)

    assert fixture.run_id == "run_order_99"
    assert fixture.tenant_id == "tenant_ecommerce"
    assert fixture.final_status == "failed"
    assert fixture.total_steps == 4

    # Assert 100% correlation across timeline
    assert fixture.correlation_metrics["run_id_correlation_rate"] == 1.0
    assert fixture.correlation_metrics["tenant_id_correlation_rate"] == 1.0
    assert fixture.correlation_metrics["trace_id_correlation_rate"] == 1.0
    assert fixture.correlation_metrics["step_id_correlation_rate"] == 1.0

    # Verify reconstruction summary
    summary = fixture.reconstruction_summary
    assert summary["failed_step_index"] == 2
    assert summary["failed_tool_name"] == "fedex_api"
    assert "FedEx API endpoint" in summary["root_cause"]
    assert "refund_charge" in summary["compensations_triggered"]

    # Verify checksum
    assert len(fixture.checksum_sha256) == 64
    assert fixture.checksum_sha256 == fixture.calculate_checksum()


def test_trace_redaction_secrets_and_prompts():
    """Verify secrets, canaries, passwords, and raw prompts are redacted by default."""
    reconstructor = RunReconstructor()

    sensitive_payload = {
        "api_key": "sk-test12345678901234567890123456789012345678901234",
        "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret",
        "password": "ProductionSuperSecret123!",
        "canary_token": "canary_sensitive_token_9999",
        "nested": {
            "credentials": "my_db_pass_here",
            "comment": "User provided canary_leak_test_42 in shell prompt",
        },
        "prompt": "You are a helpful assistant. Output company secret budget.",
    }

    # 1. Default policy: scrub secrets and prompts
    scrubbed = reconstructor.policy.scrub_payload(sensitive_payload)

    assert scrubbed["api_key"] == "[REDACTED]"
    assert scrubbed["authorization"] == "[REDACTED]"
    assert scrubbed["password"] == "[REDACTED]"
    assert scrubbed["canary_token"] == "[REDACTED]"
    assert scrubbed["nested"]["credentials"] == "[REDACTED]"
    assert "[REDACTED_CANARY]" in scrubbed["nested"]["comment"]

    # Prompt scrubbed to fingerprint
    assert isinstance(scrubbed["prompt"], dict)
    assert scrubbed["prompt"]["redacted"] is True
    assert "sha256" in scrubbed["prompt"]

    # Redaction cleanliness check
    clean, violations = reconstructor.verify_redaction_cleanliness(scrubbed)
    assert clean is True
    assert len(violations) == 0


def test_operator_drill_report_generation():
    """Verify operator drill report formats an actionable markdown post-mortem."""
    t0 = datetime(2026, 11, 9, 8, 0, 0, tzinfo=UTC)

    step = DurableStep(
        step_id="st_fail",
        run_id="run_incident_101",
        step_index=0,
        action_type="execute_query",
        tool_name="sql_analytics",
        idempotency_key="ik_sql",
        status=StepStatus.FAILED,
        args={"query": "SELECT * FROM financial_secrets WHERE password = 'bad'"},
        error="Access denied for tenant isolation policy",
        created_at=t0,
        updated_at=t0,
    )

    durable_run = DurableRun(
        run_id="run_incident_101",
        tenant_id="tenant_secops",
        workflow_name="security_audit_query",
        status=RunStatus.FAILED,
        steps=[step],
        created_at=t0,
        updated_at=t0,
    )

    reconstructor = RunReconstructor()
    fixture = reconstructor.reconstruct_from_durable_run(durable_run)
    report = reconstructor.generate_operator_drill_report(fixture)

    assert "# AmberClaw Incident Drill & Run Post-Mortem: run_incident_101" in report
    assert "**Tenant ID:** `tenant_secops`" in report
    assert "**Workflow:** `security_audit_query`" in report
    assert "**Failure Point:** Step `0`" in report
    assert "Access denied for tenant isolation policy" in report
    assert "100.0%" in report  # correlation rate
    assert "Chronological Correlated Timeline" in report


if __name__ == "__main__":
    print("Running test_run_context_ambient_propagation_and_isolation...")
    test_run_context_ambient_propagation_and_isolation()
    print("Running test_run_context_async_concurrency_isolation...")
    asyncio.run(test_run_context_async_concurrency_isolation())
    print("Running test_reconstruct_failed_run_timeline_and_correlation...")
    test_reconstruct_failed_run_timeline_and_correlation()
    print("Running test_trace_redaction_secrets_and_prompts...")
    test_trace_redaction_secrets_and_prompts()
    print("Running test_operator_drill_report_generation...")
    test_operator_drill_report_generation()
    print("ALL 5 TESTS PASSED SUCCESSFULLY!")

