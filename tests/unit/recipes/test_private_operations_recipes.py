# ruff: noqa: PLR2004
"""Unit tests for CL-021: Three Complete Private-Operations Recipes."""

from __future__ import annotations

import pytest

from amberclaw.recipes.base import RecipeStatus
from amberclaw.recipes.cited_knowledge import CitedKnowledgeRecipe
from amberclaw.recipes.incident_investigation import IncidentInvestigationRecipe
from amberclaw.recipes.scheduled_report import ScheduledReportRecipe
from amberclaw.security.approval import ToolApprovalManager


@pytest.fixture(autouse=True)
def reset_approval_manager():
    mgr = ToolApprovalManager.get_instance()
    mgr._tickets.clear()
    yield
    mgr._tickets.clear()


@pytest.mark.asyncio
async def test_recipe_1_cited_knowledge_valid_answer():
    """Verify Recipe 1 extracts accurate cited answers from private documentation."""
    recipe = CitedKnowledgeRecipe()

    docs = [
        {
            "id": "doc_sec_01",
            "text": "AmberClaw enforces kernel-level network isolation using Landlock and seccomp system filters.",
            "timestamp": "2026-01-10T00:00:00Z",
        },
        {
            "id": "doc_sec_02",
            "text": "The maximum allowed memory footprint for the minimal base runtime is under 100 MB RSS.",
            "timestamp": "2026-02-15T00:00:00Z",
        },
    ]

    res = await recipe.execute(
        query="How does AmberClaw isolate network access?",
        documents=docs,
    )

    assert res.status == RecipeStatus.COMPLETED
    assert res.safety_checks_passed is True
    assert "doc_sec_01" in res.final_state["citations"]
    assert res.final_state["abstained"] is False
    assert res.actual_cost_usd > 0.0


@pytest.mark.asyncio
async def test_recipe_1_cited_knowledge_abstains_on_contradiction():
    """Verify Recipe 1 explicitly abstains when encountering contradictory temporal facts."""
    recipe = CitedKnowledgeRecipe()

    docs = [
        {
            "id": "policy_v1",
            "text": "Maximum database connection pool size is strictly set to 5 connections.",
            "timestamp": "2025-01-01T00:00:00Z",
        },
        {
            "id": "policy_v2",
            "text": "Maximum database connection pool size is strictly set to 50 connections.",
            "timestamp": "2025-01-01T00:00:00Z",  # Identical timestamp = unresolved conflict
        },
    ]

    res = await recipe.execute(
        query="What is the database connection pool limit?",
        documents=docs,
    )

    assert res.status == RecipeStatus.COMPLETED
    assert res.final_state["abstained"] is True
    assert res.final_state["contradiction_detected"] is True
    assert "contradictory" in res.final_state["abstention_reason"].lower()


@pytest.mark.asyncio
async def test_recipe_2_incident_investigation_approval_flow():
    """Verify Recipe 2 isolates root cause, halts at approval gate, and executes on approval."""
    recipe = IncidentInvestigationRecipe()

    logs = [
        "2026-11-09 08:30:12 WARN [egress_monitor] outbound connection to unknown host 198.51.100.42 attempted on port 443",
        "2026-11-09 08:30:13 ALERT [seccomp_filter] blocked unauthorized connect syscall",
    ]

    # Step 1: Initiate triage
    res = await recipe.initiate_investigation(
        incident_id="inc_8829",
        alert_type="unauthorized_egress",
        logs=logs,
    )

    assert res.status == RecipeStatus.WAITING_FOR_APPROVAL
    assert res.approval_ticket_id is not None
    assert "block_network_ip" in res.final_state["proposed_action"]

    # Step 2: Operator reviews and approves
    final = await recipe.finalize_remediation(
        ticket_id=res.approval_ticket_id,
        approved=True,
        operator_notes="Confirmed unauthorized egress attempt, firewall block authorized.",
    )

    assert final.status == RecipeStatus.COMPLETED
    assert final.final_state["remediation_status"] == "executed"
    assert final.final_state["action"] == "block_network_ip"


@pytest.mark.asyncio
async def test_recipe_2_incident_investigation_rejection_and_rollback():
    """Verify Recipe 2 triggers safe rollback when operator rejects remediation proposal."""
    recipe = IncidentInvestigationRecipe()

    logs = [
        "2026-11-09 08:45:00 WARN [auth] failed login threshold exceeded for operator_service",
    ]

    res = await recipe.initiate_investigation(
        incident_id="inc_8830",
        alert_type="brute_force",
        logs=logs,
    )
    assert res.status == RecipeStatus.WAITING_FOR_APPROVAL

    # Operator rejects
    final = await recipe.finalize_remediation(
        ticket_id=res.approval_ticket_id,
        approved=False,
        operator_notes="Known load test run by QA team; suppression authorized.",
    )

    assert final.status == RecipeStatus.ROLLED_BACK
    assert final.final_state["remediation_status"] == "rejected_and_rolled_back"


@pytest.mark.asyncio
async def test_recipe_3_scheduled_report_approval_and_dispatch():
    """Verify Recipe 3 aggregates operational data and enforces delivery approval."""
    recipe = ScheduledReportRecipe()

    metrics = {
        "total_runs": 1420,
        "successful_runs": 1415,
        "total_spend_usd": 4.8215,
        "p95_latency_ms": 182.4,
    }

    # Step 1: Compile report requiring approval
    res = await recipe.compile_report(
        report_period="2026-W45",
        metrics=metrics,
        destination_channel="secops_digest_email",
        require_approval_before_send=True,
    )

    assert res.status == RecipeStatus.WAITING_FOR_APPROVAL
    assert res.approval_ticket_id is not None
    assert "Total Workflow Runs" in res.final_state["report_markdown"]
    assert "1420" in res.final_state["report_markdown"]
    assert res.actual_cost_usd > 0.0

    # Step 2: Operator grants delivery approval
    final = await recipe.approve_and_dispatch(
        ticket_id=res.approval_ticket_id,
        approved=True,
    )
    assert final.status == RecipeStatus.COMPLETED
    assert final.final_state["delivery_status"] == "dispatched_to_channel"
