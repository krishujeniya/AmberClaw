"""Unit tests for AmberClaw governance policies, multi-stage approval workflows, and rollback engine."""

import pytest

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
from amberclaw.governance.workflow import (
    WorkflowEngine,
    WorkflowStage,
)

EXPECTED_ROLLBACK_STEPS = 2


def test_policy_engine_evaluation():
    engine = PolicyEngine()

    # 1. Standard safe action -> ALLOW
    res_safe = engine.evaluate(action_name="read_file", content="cat document.txt", cost_estimate=0.01)
    assert res_safe.is_allowed is True
    assert res_safe.requires_approval is False
    assert res_safe.enforcement == EnforcementAction.ALLOW

    # 2. Root execution command -> DENY (POL-001)
    res_root = engine.evaluate(action_name="bash", content="sudo rm -rf /var/log", cost_estimate=0.01)
    assert res_root.is_allowed is False
    assert res_root.enforcement == EnforcementAction.DENY
    assert "POL-001-ROOT-EXEC" in res_root.triggered_policies

    # 3. High cost turn -> REQUIRE_APPROVAL (POL-002)
    res_cost = engine.evaluate(action_name="llm_query", content="Summarize big dataset", cost_estimate=12.50)
    assert res_cost.is_allowed is True
    assert res_cost.requires_approval is True
    assert res_cost.enforcement == EnforcementAction.REQUIRE_APPROVAL

    # 4. Custom policy rule
    engine.add_policy(
        PolicyRule(
            policy_id="POL-CUSTOM-API",
            name="Require review for external webhooks",
            target_actions=["webhook"],
            enforcement=EnforcementAction.REQUIRE_APPROVAL,
        )
    )
    res_custom = engine.evaluate(action_name="webhook", content="https://api.stripe.com/v1/refunds")
    assert res_custom.requires_approval is True


def test_approval_workflow_engine():
    wf = WorkflowEngine()

    # Submit request with 2 required approvals
    req = wf.submit_request(
        requester_id="agent_finops",
        title="Increase API budget allocation",
        description="Raise monthly budget limit to $500",
        required_approvals=2,
    )
    assert req.stage == WorkflowStage.HUMAN_REVIEW
    assert req.approval_count == 0
    assert not req.is_finalized

    # Cast 1st approval vote
    req = wf.cast_vote(
        request_id=req.request_id,
        reviewer_id="lead_eng",
        approved=True,
        comments="Looks good technically",
    )
    assert req.stage == WorkflowStage.HUMAN_REVIEW
    assert req.approval_count == 1

    # Cast 2nd approval vote -> stage transitions to APPROVED
    req = wf.cast_vote(
        request_id=req.request_id,
        reviewer_id="cfo",
        approved=True,
        comments="Budget approved",
    )
    assert req.stage == WorkflowStage.APPROVED
    assert req.is_finalized is True

    # Attempting to vote on finalized request raises ValueError
    with pytest.raises(ValueError):
        wf.cast_vote(request_id=req.request_id, reviewer_id="extra_reviewer", approved=True)


def test_approval_workflow_rejection():
    wf = WorkflowEngine()
    req = wf.submit_request(
        requester_id="agent_ops",
        title="Drop production database replica",
        required_approvals=2,
    )

    req = wf.cast_vote(
        request_id=req.request_id,
        reviewer_id="security_lead",
        approved=False,
        comments="Rejected due to active queries",
    )
    assert req.stage == WorkflowStage.REJECTED
    assert req.is_finalized is True


def test_governance_rollback_manager():
    mgr = GovernanceRollbackManager()

    # Register custom file rollback handler
    restored_files: list[str] = []

    def custom_file_restore(step: RollbackStep) -> bool:
        restored_files.append(step.target)
        return True

    mgr.register_handler("file_restore", custom_file_restore)

    plan = mgr.create_plan(action_id="ACT-MIGRATE-DATA")
    mgr.add_step(
        plan_id=plan.plan_id,
        action_type="file_restore",
        target="/var/data/schema.sql",
        parameters={"backup_path": "/var/backup/schema.sql.bak"},
    )
    mgr.add_step(
        plan_id=plan.plan_id,
        action_type="noop",
        target="system_state",
    )

    executed_plan = mgr.execute_plan(plan.plan_id)
    assert executed_plan.status == RollbackStatus.COMPLETED
    assert len(executed_plan.steps) == EXPECTED_ROLLBACK_STEPS
    assert all(s.status == RollbackStatus.COMPLETED for s in executed_plan.steps)
    assert "/var/data/schema.sql" in restored_files
