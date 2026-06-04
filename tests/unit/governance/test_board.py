"""Unit tests for GovernanceBoard and TicketSystem integration."""

import asyncio

import pytest

from amberclaw.governance.board import ActionProposal, GovernanceBoard, RiskLevel
from amberclaw.governance.tickets import TicketStatus, tickets


@pytest.mark.anyio
async def test_governance_board_auto_approve():
    board = GovernanceBoard(require_human_approval_above=RiskLevel.HIGH, max_auto_budget=10.0)
    proposal = ActionProposal(
        action_id="act_001",
        agent_id="agent_test",
        description="Clean temp directory",
        risk_level=RiskLevel.LOW,
        cost_estimate=1.0,
    )
    result = await board.evaluate_proposal(proposal)
    assert result is True


@pytest.mark.anyio
async def test_governance_board_high_risk_requires_approval():
    board = GovernanceBoard(require_human_approval_above=RiskLevel.HIGH, max_auto_budget=10.0)
    proposal = ActionProposal(
        action_id="act_002",
        agent_id="agent_test",
        description="Delete database table",
        risk_level=RiskLevel.HIGH,
        cost_estimate=1.0,
    )

    # We run the task in the background since it will await a ticket resolution
    task = asyncio.create_task(board.evaluate_proposal(proposal))

    # Give the task a moment to create the ticket
    await asyncio.sleep(0.1)

    pending_tickets = tickets.get_pending_tickets()
    assert len(pending_tickets) == 1
    ticket = pending_tickets[0]
    assert ticket.context["proposal_id"] == "act_002"

    # Resolve the ticket as approved
    tickets.resolve_ticket(ticket.id, TicketStatus.APPROVED, reviewer_id="operator_test")

    # Await the result of evaluation
    result = await task
    assert result is True


@pytest.mark.anyio
async def test_governance_board_high_risk_rejected():
    board = GovernanceBoard(require_human_approval_above=RiskLevel.HIGH, max_auto_budget=10.0)
    proposal = ActionProposal(
        action_id="act_003",
        agent_id="agent_test",
        description="Write payload to root partition",
        risk_level=RiskLevel.CRITICAL,
        cost_estimate=1.0,
    )

    task = asyncio.create_task(board.evaluate_proposal(proposal))
    await asyncio.sleep(0.1)

    pending_tickets = tickets.get_pending_tickets()
    # Find the ticket created for this proposal
    ticket = next(t for t in pending_tickets if t.context.get("proposal_id") == "act_003")

    # Resolve the ticket as rejected
    tickets.resolve_ticket(ticket.id, TicketStatus.REJECTED, reviewer_id="operator_test")

    result = await task
    assert result is False


@pytest.mark.anyio
async def test_governance_board_budget_exceeded():
    board = GovernanceBoard(require_human_approval_above=RiskLevel.HIGH, max_auto_budget=1.0)
    proposal = ActionProposal(
        action_id="act_004",
        agent_id="agent_test",
        description="Run heavy prompt analysis",
        risk_level=RiskLevel.LOW,
        cost_estimate=5.0,  # Exceeds max_auto_budget of 1.0
    )

    task = asyncio.create_task(board.evaluate_proposal(proposal))
    await asyncio.sleep(0.1)

    pending_tickets = tickets.get_pending_tickets()
    ticket = next(t for t in pending_tickets if t.context.get("proposal_id") == "act_004")

    # Resolve the ticket as approved
    tickets.resolve_ticket(ticket.id, TicketStatus.APPROVED, reviewer_id="operator_test")

    result = await task
    assert result is True
