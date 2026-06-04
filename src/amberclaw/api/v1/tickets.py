"""FastAPI routes for human-in-the-loop governance tickets."""

from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from amberclaw.governance.tickets import tickets, Ticket, TicketStatus

router = APIRouter()


class TicketResolveRequest(BaseModel):
    status: TicketStatus
    reviewer_id: str


@router.get("/pending", response_model=list[Ticket])
async def list_pending_tickets() -> list[Ticket]:
    """List all pending governance tickets requiring operator approval."""
    return tickets.get_pending_tickets()


@router.post("/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: str, request: TicketResolveRequest) -> dict[str, Any]:
    """Resolve a pending ticket (Approve or Reject)."""
    success = tickets.resolve_ticket(
        ticket_id=ticket_id,
        status=request.status,
        reviewer_id=request.reviewer_id,
    )
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Ticket {ticket_id} not found or already resolved.",
        )
    return {"status": "success", "message": f"Ticket {ticket_id} resolved as {request.status}."}
