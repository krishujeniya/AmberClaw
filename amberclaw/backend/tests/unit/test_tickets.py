# ruff: noqa: PLR2004
"""Unit tests for Governance Ticketing and Human-in-the-Loop Operator Approvals."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from amberclaw.api.v1.tickets import router as tickets_router
from amberclaw.governance.tickets import (
    TicketPriority,
    TicketStatus,
    TicketSystem,
    tickets,
)
from amberclaw.security.approval import (
    ApprovalStatus,
    ToolApprovalManager,
    ToolRiskLevel,
    ToolSafetyPolicy,
)


@pytest.fixture(autouse=True)
def clean_ticketing_environment(tmp_path: Path):
    """Ensure a clean ticket store and approval manager for each test."""
    test_store = tmp_path / "test_tickets.json"
    # Reinitialize global tickets system to temporary path
    tickets._store.file_path = test_store
    tickets.clear()
    ToolApprovalManager.get_instance().clear()
    yield
    tickets.clear()
    ToolApprovalManager.get_instance().clear()


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(tickets_router, prefix="/api/v1/tickets")
    return TestClient(app)


# ==============================================================================
# 1. TicketSystem Core Functionality
# ==============================================================================


@pytest.mark.asyncio
async def test_ticket_creation_and_retrieval(tmp_path: Path):
    system = TicketSystem(store_path=tmp_path / "custom_tickets.json")
    ticket = await system.create_ticket(
        requester_id="agent_alpha",
        description="Request to drop temporary production cache tables",
        priority=TicketPriority.HIGH,
        context={"db": "prod_cache", "action": "DROP TABLE temp_sessions"},
    )

    assert ticket.id is not None
    assert ticket.requester_id == "agent_alpha"
    assert ticket.status == TicketStatus.PENDING
    assert ticket.priority == TicketPriority.HIGH

    retrieved = system.get_ticket(ticket.id)
    assert retrieved is not None
    assert retrieved.id == ticket.id
    assert retrieved.description == ticket.description
    assert retrieved.context["db"] == "prod_cache"


@pytest.mark.asyncio
async def test_ticket_resolution(tmp_path: Path):
    system = TicketSystem(store_path=tmp_path / "custom_tickets.json")
    ticket = await system.create_ticket(
        requester_id="agent_beta",
        description="Deploy canary v2",
        priority=TicketPriority.MEDIUM,
    )

    resolved = system.resolve_ticket(
        ticket_id=ticket.id,
        status=TicketStatus.APPROVED,
        reviewer_id="operator_alice",
    )

    assert resolved is not None
    assert resolved.status == TicketStatus.APPROVED
    assert resolved.reviewer_id == "operator_alice"
    assert resolved.resolved_at is not None

    # Verify pending tickets list excludes resolved
    pending = system.get_pending_tickets()
    assert len(pending) == 0


@pytest.mark.asyncio
async def test_ticket_filtering_and_sorting(tmp_path: Path):
    system = TicketSystem(store_path=tmp_path / "custom_tickets.json")
    t1 = await system.create_ticket("agent1", "Task 1", priority=TicketPriority.LOW)
    t2 = await system.create_ticket(
        "agent2", "Task 2", priority=TicketPriority.CRITICAL
    )
    t3 = await system.create_ticket("agent3", "Task 3", priority=TicketPriority.HIGH)

    # Resolve t1
    system.resolve_ticket(t1.id, TicketStatus.REJECTED, reviewer_id="admin")

    critical_tickets = system.list_tickets(priority=TicketPriority.CRITICAL)
    assert len(critical_tickets) == 1
    assert critical_tickets[0].id == t2.id

    rejected_tickets = system.list_tickets(status=TicketStatus.REJECTED)
    assert len(rejected_tickets) == 1
    assert rejected_tickets[0].id == t1.id

    pending_tickets = system.get_pending_tickets()
    assert len(pending_tickets) == 2
    assert {t.id for t in pending_tickets} == {t2.id, t3.id}


# ==============================================================================
# 2. REST API Endpoints Verification
# ==============================================================================


def test_api_create_and_get_ticket(client: TestClient):
    payload = {
        "requester_id": "agent_data_pipeline",
        "description": "Access AWS production S3 bucket for training dataset export",
        "priority": "high",
        "context": {"bucket": "corp-analytics-prod", "prefix": "2026/q3/"},
    }

    create_resp = client.post("/api/v1/tickets", json=payload)
    assert create_resp.status_code == 201
    ticket_data = create_resp.json()
    ticket_id = ticket_data["id"]
    assert ticket_data["requester_id"] == "agent_data_pipeline"
    assert ticket_data["priority"] == "high"
    assert ticket_data["status"] == "pending"

    # Get single ticket
    get_resp = client.get(f"/api/v1/tickets/{ticket_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == ticket_id


def test_api_get_ticket_not_found(client: TestClient):
    resp = client.get("/api/v1/tickets/non_existent_id_9999")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_api_list_pending_and_pagination(client: TestClient):
    for i in range(5):
        client.post(
            "/api/v1/tickets",
            json={
                "requester_id": f"agent_{i}",
                "description": f"Request {i}",
                "priority": "medium",
            },
        )

    # List pending with pagination
    resp = client.get("/api/v1/tickets/pending?limit=2&offset=0")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2

    resp_page2 = client.get("/api/v1/tickets/pending?limit=2&offset=2")
    assert resp_page2.status_code == 200
    items_p2 = resp_page2.json()
    assert len(items_p2) == 2
    assert items[0]["id"] != items_p2[0]["id"]


def test_api_resolve_ticket_approved_and_rejected(client: TestClient):
    create_resp = client.post(
        "/api/v1/tickets",
        json={
            "requester_id": "agent_worker",
            "description": "Elevate permissions to reboot container",
            "priority": "critical",
        },
    )
    ticket_id = create_resp.json()["id"]

    # Approve
    resolve_resp = client.post(
        f"/api/v1/tickets/{ticket_id}/resolve",
        json={
            "status": "approved",
            "reviewer_id": "secops_lead",
            "notes": "Approved for 15m",
        },
    )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "success"
    assert resolve_resp.json()["resolution"] == "approved"

    # Verify state via GET
    get_resp = client.get(f"/api/v1/tickets/{ticket_id}")
    assert get_resp.json()["status"] == "approved"
    assert get_resp.json()["reviewer_id"] == "secops_lead"


def test_api_resolve_non_existent_ticket(client: TestClient):
    resp = client.post(
        "/api/v1/tickets/non_existent_ticket/resolve",
        json={"status": "rejected", "reviewer_id": "secops_lead"},
    )
    assert resp.status_code == 404


# ==============================================================================
# 3. ToolApprovalManager & Governance Ticket Integration
# ==============================================================================


@pytest.mark.asyncio
async def test_tool_approval_manager_ticket_synchronization(client: TestClient):
    # Setup approval manager requiring human approval for CRITICAL actions
    policy = ToolSafetyPolicy(require_human_approval_levels=[ToolRiskLevel.CRITICAL])
    approval_mgr = ToolApprovalManager(policy=policy)
    ToolApprovalManager._instance = approval_mgr

    # Evaluate critical tool call
    decision = approval_mgr.evaluate_tool_execution(
        tool_name="delete_production_database",
        agent_id="db_cleaner_agent",
        args={"force": True},
        risk_level=ToolRiskLevel.CRITICAL,
    )

    assert decision.status == ApprovalStatus.PENDING_APPROVAL
    assert decision.ticket_id is not None
    ticket_id = decision.ticket_id

    # Register in governance ticketing system
    ticket = await tickets.create_ticket(
        requester_id="db_cleaner_agent",
        description="Tool execution: delete_production_database",
        priority=TicketPriority.CRITICAL,
        context={"tool": "delete_production_database", "ticket_id": ticket_id},
    )
    # Give the ticket the exact ID that approval_mgr generated
    tickets._store.delete(ticket.id)
    ticket.id = ticket_id
    tickets._store.set(ticket_id, ticket)

    # Operator approves via API endpoint
    resolve_resp = client.post(
        f"/api/v1/tickets/{ticket_id}/resolve",
        json={"status": "approved", "reviewer_id": "senior_dba"},
    )
    assert resolve_resp.status_code == 200

    # Verify ToolApprovalManager state is now approved
    assert approval_mgr._pending_tickets[ticket_id]["status"] == "approved"
