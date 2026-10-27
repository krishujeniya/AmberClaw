"""Domain models for Human-in-the-loop approvals, tasks, and governance tickets."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TicketStatus(StrEnum):
    OPEN = "open"
    PENDING_APPROVAL = "pending_approval"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REJECTED = "rejected"


class TicketPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketModel(BaseModel):
    """Ticket entity representing action approval or operational requests."""

    id: str = Field(..., description="Unique ticket identifier.")
    title: str = Field(..., description="Short summary of ticket request.")
    description: str = Field(default="", description="Detailed context or rationale.")
    status: TicketStatus = Field(default=TicketStatus.PENDING_APPROVAL)
    priority: TicketPriority = Field(default=TicketPriority.MEDIUM)
    requester_id: str = Field(..., description="Agent or User ID requesting the action.")
    assignee_id: str | None = Field(default=None, description="Assigned approver or agent ID.")
    tool_call_payload: dict[str, Any] | None = Field(
        default=None, description="Proposed tool call payload pending governance sign-off."
    )
    resolution_notes: str | None = Field(default=None, description="Notes attached upon resolution/rejection.")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
