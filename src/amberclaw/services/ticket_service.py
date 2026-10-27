"""Ticket service encapsulating human-in-the-loop governance ticket operations."""

from typing import Any

from loguru import logger

from amberclaw.governance.tickets import (
    Ticket,
    TicketPriority,
    TicketStatus,
    TicketSystem,
    tickets,
)
from amberclaw.security.approval import ToolApprovalManager
from amberclaw.security.audit import AuditEvent, SecurityAuditLogger


class TicketService:
    """Service orchestrating human review tickets and operator approvals with audit logging."""

    def __init__(
        self,
        ticket_system: TicketSystem | None = None,
        audit_logger: SecurityAuditLogger | None = None,
    ) -> None:
        self.ticket_system = ticket_system or tickets
        self.audit_logger = audit_logger or SecurityAuditLogger.get_logger()

    async def create_ticket(
        self,
        requester_id: str,
        description: str,
        priority: TicketPriority = TicketPriority.MEDIUM,
        context: dict[str, Any] | None = None,
    ) -> Ticket:
        """Create a new governance review ticket and emit an audit event."""
        ticket = await self.ticket_system.create_ticket(
            requester_id=requester_id,
            description=description,
            priority=priority,
            context=context or {},
        )

        self.audit_logger.log_event(
            AuditEvent(
                actor=requester_id,
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
        logger.info(
            "Ticket [{}] created by requester '{}' (priority: {})",
            ticket.id,
            requester_id,
            priority,
        )
        return ticket

    def list_tickets(
        self,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Ticket]:
        """List governance tickets with optional filtering and pagination."""
        items = self.ticket_system.list_tickets(status=status, priority=priority)
        return items[offset : offset + limit]

    def get_pending_tickets(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Ticket]:
        """List all pending tickets requiring review."""
        items = self.ticket_system.get_pending_tickets()
        return items[offset : offset + limit]

    def get_ticket(self, ticket_id: str) -> Ticket | None:
        """Fetch a specific ticket by identifier."""
        return self.ticket_system.get_ticket(ticket_id)

    async def resolve_ticket(
        self,
        ticket_id: str,
        status: TicketStatus,
        reviewer_id: str,
        notes: str | None = None,
    ) -> Ticket:
        """Resolve a pending ticket with approval or rejection."""
        ticket = self.ticket_system.get_ticket(ticket_id)
        if not ticket:
            raise KeyError(f"Ticket '{ticket_id}' not found.")

        resolved = self.ticket_system.resolve_ticket(
            ticket_id=ticket_id,
            status=status,
            reviewer_id=reviewer_id,
        )

        # Notify ToolApprovalManager if this ticket corresponds to a paused tool call
        approval_mgr = ToolApprovalManager.get_instance()
        approved = status == TicketStatus.APPROVED
        approval_mgr.resolve_ticket(
            ticket_id=ticket_id, approved=approved, reviewer=reviewer_id
        )

        self.audit_logger.log_event(
            AuditEvent(
                actor=reviewer_id,
                action=f"governance.ticket_{status.value}",
                resource_type="governance_ticket",
                resource_id=ticket.id,
                outcome="success",
                metadata={"notes": notes, "status": status.value},
            )
        )
        logger.info(
            "Ticket [{}] resolved as {} by '{}'", ticket_id, status.value, reviewer_id
        )
        return resolved
