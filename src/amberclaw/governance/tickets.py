import uuid
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from amberclaw.storage.persistence import JSONStateStore


class TicketPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Ticket(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    requester_id: str
    description: str
    priority: TicketPriority = TicketPriority.MEDIUM
    status: TicketStatus = TicketStatus.PENDING
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None
    reviewer_id: str | None = None


class TicketSystem:
    """A centralized ticketing system for managing tasks and human approvals."""

    def __init__(
        self,
        store_path: Path | str | None = None,
        data_dir: Path | str | None = None,
    ) -> None:
        if data_dir:
            path = Path(data_dir) / "tickets.json"
        elif store_path:
            path = Path(store_path)
        else:
            path = Path("~/.amberclaw/tickets.json").expanduser()

        self._store = JSONStateStore(file_path=path, model_cls=Ticket)

    async def create_ticket(
        self,
        requester_id: str,
        description: str,
        priority: TicketPriority = TicketPriority.MEDIUM,
        context: dict[str, Any] | None = None,
    ) -> Ticket:
        """Create a new ticket in the system."""
        ticket = Ticket(
            requester_id=requester_id,
            description=description,
            priority=priority,
            context=context or {},
        )
        self._store.set(ticket.id, ticket)
        return ticket

    def get_ticket(self, ticket_id: str) -> Ticket | None:
        """Retrieve a ticket by its ID."""
        return self._store.get(ticket_id)

    def resolve_ticket(
        self,
        ticket_id: str,
        status: TicketStatus,
        reviewer_id: str | None = None,
    ) -> Ticket | None:
        """Approve or reject a ticket."""
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return None

        ticket.status = status
        ticket.resolved_at = datetime.now(UTC)
        ticket.reviewer_id = reviewer_id
        self._store.set(ticket_id, ticket)
        return ticket

    def get_pending_tickets(self) -> list[Ticket]:
        """Get all tickets that are still pending."""
        all_tickets = list(self._store.get_all().values())
        return [t for t in all_tickets if t.status == TicketStatus.PENDING]

    def list_tickets(
        self,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
    ) -> list[Ticket]:
        """List all tickets with optional status and priority filters."""
        all_tickets = list(self._store.get_all().values())
        filtered = all_tickets
        if status:
            filtered = [t for t in filtered if t.status == status]
        if priority:
            filtered = [t for t in filtered if t.priority == priority]
        return sorted(filtered, key=lambda t: t.created_at, reverse=True)

    def clear(self) -> None:
        """Clear all tickets in the system store."""
        self._store.clear()


tickets = TicketSystem()
