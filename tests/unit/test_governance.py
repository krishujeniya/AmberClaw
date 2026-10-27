# ruff: noqa: PLR2004
"""Unit tests for AmberClaw Governance subsystem:
- GovernanceBoard (risk escalation, auto-budget checks, human-in-the-loop tickets)
- PolicyEngine (default & custom rules, enforcement actions, forbidden tokens)
- GovernanceRollbackManager (compensatory actions, custom handlers)
- WorkflowEngine (multi-stage approval, voting, expiration)
- AuditLogger (tamper-evident hash chaining, audit querying)
"""

import asyncio
from pathlib import Path

import pytest

from amberclaw.governance.audit import AuditAction, AuditLogger, AuditQuery
from amberclaw.governance.board import ActionProposal, GovernanceBoard, RiskLevel
from amberclaw.governance.policies import (
    EnforcementAction,
    PolicyEngine,
    PolicyRule,
)
from amberclaw.governance.rollback import (
    GovernanceRollbackManager,
    RollbackStatus,
    RollbackStep,
)
from amberclaw.governance.tickets import TicketStatus, tickets
from amberclaw.governance.workflow import (
    WorkflowEngine,
    WorkflowStage,
)


@pytest.fixture(autouse=True)
def clean_governance_env(tmp_path: Path):
    test_store = tmp_path / "gov_tickets.json"
    tickets._store.file_path = test_store
    tickets.clear()
    yield
    tickets.clear()


# ==============================================================================
# 1. Governance Board & Risk Escalation
# ==============================================================================


@pytest.mark.asyncio
async def test_governance_board_auto_approval_low_risk():
    board = GovernanceBoard(
        require_human_approval_above=RiskLevel.HIGH,
        max_auto_budget=2.0,
    )
    proposal = ActionProposal(
        action_id="act_low_001",
        agent_id="research_agent",
        description="Search documentation online",
        risk_level=RiskLevel.LOW,
        cost_estimate=0.05,
    )

    approved = await board.evaluate_proposal(proposal)
    assert approved is True


@pytest.mark.asyncio
async def test_governance_board_escalates_on_high_risk_and_resolves():
    board = GovernanceBoard(
        require_human_approval_above=RiskLevel.HIGH,
        max_auto_budget=5.0,
    )
    proposal = ActionProposal(
        action_id="act_high_002",
        agent_id="ops_agent",
        description="Truncate database logs table",
        risk_level=RiskLevel.HIGH,
        cost_estimate=0.50,
    )

    # Launch evaluation asynchronously
    eval_task = asyncio.create_task(board.evaluate_proposal(proposal))

    # Wait for the ticket to appear in tickets system
    await asyncio.sleep(0.1)
    pending_tickets = tickets.get_pending_tickets()
    assert len(pending_tickets) == 1
    ticket = pending_tickets[0]
    assert ticket.context["proposal_id"] == "act_high_002"

    # Operator approves ticket
    tickets.resolve_ticket(ticket.id, TicketStatus.APPROVED, reviewer_id="sec_lead")

    result = await eval_task
    assert result is True


@pytest.mark.asyncio
async def test_governance_board_escalates_on_exceeding_budget():
    board = GovernanceBoard(
        require_human_approval_above=RiskLevel.HIGH,
        max_auto_budget=1.0,
    )
    proposal = ActionProposal(
        action_id="act_budget_003",
        agent_id="ml_trainer",
        description="Launch 8x A100 GPU fine-tuning job",
        risk_level=RiskLevel.LOW,
        cost_estimate=25.0,  # Exceeds max_auto_budget 1.0
    )

    eval_task = asyncio.create_task(board.evaluate_proposal(proposal))
    await asyncio.sleep(0.1)

    pending = tickets.get_pending_tickets()
    assert len(pending) == 1
    # Operator rejects ticket
    tickets.resolve_ticket(pending[0].id, TicketStatus.REJECTED, reviewer_id="fin_lead")

    result = await eval_task
    assert result is False


# ==============================================================================
# 2. Policy Engine
# ==============================================================================


def test_policy_engine_default_rules_enforce_boundaries():
    engine = PolicyEngine()

    # Rule POL-001 forbids root / sudo commands
    result_sudo = engine.evaluate(action_name="terminal", content="sudo rm -rf /")
    assert result_sudo.is_allowed is False
    assert result_sudo.enforcement == EnforcementAction.DENY
    assert any("POL-001" in p for p in result_sudo.triggered_policies)

    # Allowed safe command
    result_safe = engine.evaluate(action_name="terminal", content="echo hello")
    assert result_safe.is_allowed is True
    assert result_safe.enforcement == EnforcementAction.ALLOW


def test_policy_engine_custom_rules_and_cost():
    engine = PolicyEngine()
    custom_rule = PolicyRule(
        policy_id="POL-CUSTOM-DATA-EXPORT",
        name="Block Data Exfiltration",
        target_actions=["export", "download"],
        max_cost=10.0,
        forbidden_tokens=["ssn", "credit_card"],
        enforcement=EnforcementAction.REQUIRE_APPROVAL,
    )
    engine.add_policy(custom_rule)

    # Triggered by forbidden token
    eval_token = engine.evaluate("export", content="user credit_card info")
    assert eval_token.requires_approval is True
    assert eval_token.enforcement == EnforcementAction.REQUIRE_APPROVAL
    assert "POL-CUSTOM-DATA-EXPORT" in eval_token.triggered_policies

    # Triggered by cost ceiling
    eval_cost = engine.evaluate("export", cost_estimate=15.0)
    assert eval_cost.requires_approval is True
    assert eval_cost.enforcement == EnforcementAction.REQUIRE_APPROVAL


# ==============================================================================
# 3. Governance Rollback Manager
# ==============================================================================


def test_rollback_manager_execution():
    manager = GovernanceRollbackManager()
    custom_executed = []

    def custom_revert(step: RollbackStep) -> bool:
        custom_executed.append(step.target)
        return True

    manager.register_handler("custom_db_revert", custom_revert)

    plan = manager.create_plan(action_id="act_migration_123")
    manager.add_step(plan.plan_id, action_type="noop", target="system_flag")
    manager.add_step(
        plan.plan_id, action_type="custom_db_revert", target="users_table_backup"
    )

    executed_plan = manager.execute_plan(plan.plan_id)
    assert executed_plan.status == RollbackStatus.COMPLETED
    assert "users_table_backup" in custom_executed


# ==============================================================================
# 4. Workflow Engine & Consensus Voting
# ==============================================================================


def test_workflow_engine_multistage_approval():
    workflow = WorkflowEngine()
    req = workflow.submit_request(
        requester_id="agent_planner",
        title="Deploy Version 2026.1",
        required_approvals=2,
        auto_pass_checks=True,
    )

    assert req.stage == WorkflowStage.HUMAN_REVIEW

    # First vote (needs 2)
    req = workflow.cast_vote(
        request_id=req.request_id,
        reviewer_id="reviewer_1",
        approved=True,
        comments="LGTM step 1",
    )
    assert req.approval_count == 1
    assert req.stage == WorkflowStage.HUMAN_REVIEW

    # Second vote (reaches threshold)
    req = workflow.cast_vote(
        request_id=req.request_id,
        reviewer_id="reviewer_2",
        approved=True,
        comments="LGTM step 2",
    )
    assert req.approval_count == 2
    assert req.stage == WorkflowStage.APPROVED
    assert req.is_finalized is True


# ==============================================================================
# 5. Tamper-Evident Audit Logger
# ==============================================================================


def test_audit_logger_hash_chaining(tmp_path: Path):
    logger = AuditLogger(log_dir=tmp_path / "gov_audit")

    r1 = logger.log_action(
        actor_id="agent_supervisor",
        action=AuditAction.AGENT_DECISION,
        details={"decision": "escalate_to_board"},
    )
    r2 = logger.log_action(
        actor_id="board_director",
        action=AuditAction.GOVERNANCE_APPROVAL,
        details={"approved": True},
    )

    assert r1.index == 0
    assert r2.index == 1
    assert r2.previous_hash == r1.hash
    assert len(r1.hash) == 64  # SHA-256 length

    # Query audit log
    query = AuditQuery(actor_id="board_director")
    results = logger.query(query)
    assert len(results) == 1
    assert results[0].action == AuditAction.GOVERNANCE_APPROVAL
    assert logger.verify_integrity() is True
