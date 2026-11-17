# ruff: noqa: S108, PLR2004
"""Tests for CL-012: Reviewable human approvals.

Verifies:
1. Approval ticket inspection (actor, exact action/arguments, destination, scope, cost, expiry, hash).
2. Immutable action binding & argument tampering prevention.
3. Replay attack prevention (single-use tickets).
4. Expiration enforcement.
5. Identity & tenant mismatch rejection.
6. Deny and cancel lifecycle.
7. Web dashboard API resolution and cancellation endpoints.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from amberclaw.security.approval import (
    ApprovalStatus,
    ToolApprovalManager,
    ToolRiskLevel,
    ToolSafetyPolicy,
    compute_arguments_hash,
)
from amberclaw.web.auth import WebAuthManager
from amberclaw.web.server import create_web_app


@pytest.fixture
def fresh_manager() -> ToolApprovalManager:
    policy = ToolSafetyPolicy(
        require_human_approval_levels=[ToolRiskLevel.HIGH, ToolRiskLevel.CRITICAL],
        ticket_ttl_seconds=300,  # 5 minutes
    )
    mgr = ToolApprovalManager(policy=policy)
    mgr.clear()
    return mgr


def test_approval_ticket_inspectability(fresh_manager: ToolApprovalManager):
    """Approval tickets expose actor, action, destination, scope, cost, and args hash."""
    args = {
        "command": "rm -rf /tmp/scratch_dir",
        "cwd": "/tmp",
        "estimated_cost_usd": 0.005,
    }

    decision = fresh_manager.evaluate_tool_execution(
        tool_name="bash",
        agent_id="remediation_agent",
        args=args,
        risk_level=ToolRiskLevel.CRITICAL,
        tenant_id="tenant_alpha",
    )

    assert decision.status == ApprovalStatus.PENDING_APPROVAL
    assert decision.ticket_id is not None
    assert decision.ticket is not None

    ticket = decision.ticket
    assert ticket.actor == "remediation_agent"
    assert ticket.tenant_id == "tenant_alpha"
    assert ticket.tool_name == "bash"
    assert ticket.destination == "/tmp"
    assert "shell:rm" in ticket.scope
    assert ticket.estimated_cost_usd == 0.005
    assert ticket.status == ApprovalStatus.PENDING_APPROVAL
    assert ticket.consumed is False

    expected_hash = compute_arguments_hash(args)
    assert ticket.args_hash == expected_hash

    # Can retrieve ticket from manager
    retrieved = fresh_manager.get_ticket(decision.ticket_id)
    assert retrieved is not None
    assert retrieved.ticket_id == decision.ticket_id


def test_argument_tampering_denied(fresh_manager: ToolApprovalManager):
    """Altering arguments between approval and execution triggers tampering detection."""
    approved_args = {"path": "/var/log/audit.log", "mode": "truncate"}

    decision = fresh_manager.evaluate_tool_execution(
        tool_name="write_file",
        agent_id="cleanup_agent",
        args=approved_args,
        risk_level=ToolRiskLevel.HIGH,
    )
    ticket_id = decision.ticket_id
    assert fresh_manager.resolve_ticket(ticket_id, approved=True, reviewer="secops_lead")

    # Attempt execution with tampered arguments
    tampered_args = {
        "path": "/etc/shadow",  # Changed target path
        "mode": "truncate",
        "approval_ticket_id": ticket_id,
    }

    exec_decision = fresh_manager.evaluate_tool_execution(
        tool_name="write_file",
        agent_id="cleanup_agent",
        args=tampered_args,
        risk_level=ToolRiskLevel.HIGH,
    )

    assert exec_decision.status == ApprovalStatus.REJECTED
    assert "tampering detected" in exec_decision.reason


def test_replay_attack_prevented(fresh_manager: ToolApprovalManager):
    """An approved ticket can only execute once; replaying the ticket is refused."""
    valid_args = {"host": "backup.internal.net", "action": "sync"}

    decision = fresh_manager.evaluate_tool_execution(
        tool_name="http_request",
        agent_id="backup_worker",
        args=valid_args,
        risk_level=ToolRiskLevel.HIGH,
    )
    ticket_id = decision.ticket_id
    assert fresh_manager.resolve_ticket(ticket_id, approved=True)

    # First execution with approved ticket
    call_args = dict(valid_args)
    call_args["approval_ticket_id"] = ticket_id

    first_run = fresh_manager.evaluate_tool_execution(
        tool_name="http_request",
        agent_id="backup_worker",
        args=call_args,
        risk_level=ToolRiskLevel.HIGH,
    )
    assert first_run.status == ApprovalStatus.APPROVED
    assert first_run.ticket is not None
    assert first_run.ticket.consumed is True

    # Replay attempt with same ticket ID and args
    second_run = fresh_manager.evaluate_tool_execution(
        tool_name="http_request",
        agent_id="backup_worker",
        args=call_args,
        risk_level=ToolRiskLevel.HIGH,
    )
    assert second_run.status == ApprovalStatus.REJECTED
    assert "already consumed" in second_run.reason
    assert "replay" in second_run.reason


def test_expired_approval_rejected(fresh_manager: ToolApprovalManager):
    """Tickets past their expiration deadline cannot be resolved or executed."""
    valid_args = {"db": "analytics_dw", "command": "vacuum"}

    decision = fresh_manager.evaluate_tool_execution(
        tool_name="delete_database",
        agent_id="dba_agent",
        args=valid_args,
        risk_level=ToolRiskLevel.CRITICAL,
    )
    ticket_id = decision.ticket_id

    # Artificially expire the ticket
    ticket = fresh_manager.get_ticket(ticket_id)
    ticket.expires_at = datetime.now(UTC) - timedelta(seconds=10)

    # Resolving expired ticket fails
    assert not fresh_manager.resolve_ticket(ticket_id, approved=True)

    # Execution attempt is rejected
    call_args = dict(valid_args)
    call_args["approval_ticket_id"] = ticket_id

    exec_decision = fresh_manager.evaluate_tool_execution(
        tool_name="delete_database",
        agent_id="dba_agent",
        args=call_args,
        risk_level=ToolRiskLevel.CRITICAL,
    )
    assert exec_decision.status == ApprovalStatus.REJECTED
    assert "expired" in exec_decision.reason


def test_identity_and_tenant_mismatch_denied(fresh_manager: ToolApprovalManager):
    """An approved ticket cannot be executed by a different agent or tenant."""
    valid_args = {"target": "cluster_node_4", "op": "restart"}

    decision = fresh_manager.evaluate_tool_execution(
        tool_name="bash",
        agent_id="ops_agent_1",
        args=valid_args,
        risk_level=ToolRiskLevel.HIGH,
        tenant_id="tenant_corp",
    )
    ticket_id = decision.ticket_id
    assert fresh_manager.resolve_ticket(ticket_id, approved=True)

    call_args = dict(valid_args)
    call_args["approval_ticket_id"] = ticket_id

    # Caller agent ID mismatch
    foreign_agent_decision = fresh_manager.evaluate_tool_execution(
        tool_name="bash",
        agent_id="unauthorized_agent_2",
        args=call_args,
        risk_level=ToolRiskLevel.HIGH,
        tenant_id="tenant_corp",
    )
    assert foreign_agent_decision.status == ApprovalStatus.REJECTED
    assert "Requester identity mismatch" in foreign_agent_decision.reason

    # Caller tenant ID mismatch
    foreign_tenant_decision = fresh_manager.evaluate_tool_execution(
        tool_name="bash",
        agent_id="ops_agent_1",
        args=call_args,
        risk_level=ToolRiskLevel.HIGH,
        tenant_id="tenant_evil",
    )
    assert foreign_tenant_decision.status == ApprovalStatus.REJECTED
    assert "Tenant identity mismatch" in foreign_tenant_decision.reason


def test_deny_and_cancel_lifecycle(fresh_manager: ToolApprovalManager):
    """Denying or cancelling a ticket prevents execution."""
    args = {"file": "/tmp/test.txt"}

    # 1. Deny flow
    d1 = fresh_manager.evaluate_tool_execution(
        tool_name="write_file",
        agent_id="agent_a",
        args=args,
        risk_level=ToolRiskLevel.HIGH,
    )
    assert fresh_manager.resolve_ticket(d1.ticket_id, approved=False, reviewer="security_officer")

    exec_denied = fresh_manager.evaluate_tool_execution(
        tool_name="write_file",
        agent_id="agent_a",
        args={"file": "/tmp/test.txt", "approval_ticket_id": d1.ticket_id},
        risk_level=ToolRiskLevel.HIGH,
    )
    assert exec_denied.status == ApprovalStatus.REJECTED
    assert "rejected" in exec_denied.reason

    # 2. Cancel flow
    d2 = fresh_manager.evaluate_tool_execution(
        tool_name="write_file",
        agent_id="agent_b",
        args=args,
        risk_level=ToolRiskLevel.HIGH,
    )
    assert fresh_manager.cancel_ticket(d2.ticket_id, reason="User changed mind")

    exec_cancelled = fresh_manager.evaluate_tool_execution(
        tool_name="write_file",
        agent_id="agent_b",
        args={"file": "/tmp/test.txt", "approval_ticket_id": d2.ticket_id},
        risk_level=ToolRiskLevel.HIGH,
    )
    assert exec_cancelled.status == ApprovalStatus.REJECTED
    assert "cancelled" in exec_cancelled.reason


def test_web_governance_api_endpoints(monkeypatch):
    """Web server governance routes allow listing, resolving, and cancelling tickets."""
    monkeypatch.setenv("WEB_ADMIN_USER", "operator")
    monkeypatch.setenv("WEB_ADMIN_PASS", "test-only-password")
    auth_mgr = WebAuthManager()
    app = create_web_app(authentication=auth_mgr)
    client = TestClient(app)

    # Login to acquire session
    login_resp = client.post("/api/web/login", json={"username": "operator", "password": "test-only-password"})
    assert login_resp.status_code == 200

    mgr = ToolApprovalManager.get_instance()
    mgr.clear()

    # Create a pending ticket
    decision = mgr.evaluate_tool_execution(
        tool_name="bash",
        agent_id="ci_runner",
        args={"command": "terraform apply -auto-approve", "destination": "aws_us_east_1"},
        risk_level=ToolRiskLevel.CRITICAL,
    )
    ticket_id = decision.ticket_id

    # List tickets via API
    list_resp = client.get("/api/governance/tickets?detail=true")
    assert list_resp.status_code == 200
    tickets = list_resp.json()
    assert len(tickets) >= 1
    found = next(t for t in tickets if t["ticket_id"] == ticket_id)
    assert found["actor"] == "ci_runner"
    assert found["destination"] == "aws_us_east_1"
    assert found["args_hash"] != ""
    assert found["status"] == "pending_approval"

    # Resolve ticket via API
    resolve_resp = client.post(
        f"/api/governance/tickets/{ticket_id}/resolve",
        json={"status": "approved", "reviewer_id": "auditor_1", "notes": "Plan reviewed"},
    )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["resolution"] == "approved"

    # Create second ticket and cancel it via API
    d2 = mgr.evaluate_tool_execution(
        tool_name="delete_database",
        agent_id="ci_runner",
        args={"db": "test_db"},
        risk_level=ToolRiskLevel.CRITICAL,
    )
    cancel_resp = client.post(
        f"/api/governance/tickets/{d2.ticket_id}/cancel",
        json={"reason": "Test finished earlier than planned"},
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["cancelled"] is True
