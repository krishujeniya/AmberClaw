"""FastAPI routes for human-in-the-loop governance tickets and operator approval."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from amberclaw.governance.tickets import (
    Ticket,
    TicketPriority,
    TicketStatus,
    tickets,
)
from amberclaw.security.approval import ToolApprovalManager
from amberclaw.security.audit import AuditEvent, SecurityAuditLogger

router = APIRouter()


class TicketCreateRequest(BaseModel):
    """Payload to create a new governance review ticket."""

    requester_id: str = Field(
        ..., description="ID of the user or agent requesting review"
    )
    description: str = Field(
        ..., description="Details and context of why review is needed"
    )
    priority: TicketPriority = Field(
        default=TicketPriority.MEDIUM, description="Operational urgency of the ticket"
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary context or payload associated with the action",
    )


class TicketResolveRequest(BaseModel):
    """Decision payload to approve or reject a governance ticket."""

    status: TicketStatus = Field(
        ..., description="Resolution status: approved or rejected"
    )
    reviewer_id: str = Field(
        ..., description="Identifier of the operator resolving the ticket"
    )
    notes: str | None = Field(
        default=None, description="Optional notes or justification for the audit log"
    )


@router.get("", response_model=list[Ticket])
async def list_tickets(
    status_filter: TicketStatus | None = Query(None, alias="status"),
    priority: TicketPriority | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[Ticket]:
    """List governance tickets with optional filtering by status and priority."""
    matching = tickets.list_tickets(status=status_filter, priority=priority)
    return matching[offset : offset + limit]


@router.get("/pending", response_model=list[Ticket])
async def list_pending_tickets(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[Ticket]:
    """List all pending governance tickets requiring operator approval."""
    pending = tickets.get_pending_tickets()
    return pending[offset : offset + limit]


@router.post("", response_model=Ticket, status_code=status.HTTP_201_CREATED)
async def create_ticket(request: TicketCreateRequest) -> Ticket:
    """Create a new human-in-the-loop governance ticket."""
    ticket = await tickets.create_ticket(
        requester_id=request.requester_id,
        description=request.description,
        priority=request.priority,
        context=request.context,
    )

    audit_logger = SecurityAuditLogger.get_logger()
    audit_logger.log_event(
        AuditEvent(
            actor=request.requester_id,
            action="governance.ticket_created",
            resource_type="governance_ticket",
            resource_id=ticket.id,
            outcome="success",
            metadata={
                "priority": ticket.priority,
                "description": ticket.description,
            },
        )
    )

    return ticket


@router.get("/{ticket_id}", response_model=Ticket)
async def get_ticket(ticket_id: str) -> Ticket:
    """Retrieve details of a specific governance ticket by ID."""
    ticket = tickets.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )
    return ticket


@router.post("/{ticket_id}/resolve")
async def resolve_ticket(
    ticket_id: str, request: TicketResolveRequest
) -> dict[str, Any]:
    """Resolve a pending ticket (Approve or Reject) and sync with security approval manager."""
    resolved_ticket = tickets.resolve_ticket(
        ticket_id=ticket_id,
        status=request.status,
        reviewer_id=request.reviewer_id,
    )
    if not resolved_ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found or already resolved.",
        )

    # Synchronize resolution with ToolApprovalManager if a matching pending ticket exists
    is_approved = request.status == TicketStatus.APPROVED
    approval_manager = ToolApprovalManager.get_instance()
    approval_manager.resolve_ticket(
        ticket_id=ticket_id,
        approved=is_approved,
        reviewer=request.reviewer_id,
    )

    # Structured audit logging
    audit_logger = SecurityAuditLogger.get_logger()
    audit_logger.log_event(
        AuditEvent(
            actor=request.reviewer_id,
            action="governance.ticket_resolved",
            resource_type="governance_ticket",
            resource_id=ticket_id,
            outcome="approved" if is_approved else "rejected",
            metadata={
                "status": request.status,
                "notes": request.notes or "",
                "resolved_at": resolved_ticket.resolved_at.isoformat()
                if resolved_ticket.resolved_at
                else None,
            },
        )
    )

    return {
        "status": "success",
        "ticket_id": ticket_id,
        "resolution": request.status,
        "message": f"Ticket {ticket_id} resolved as {request.status}.",
    }
