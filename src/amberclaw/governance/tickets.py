"""
AmberClaw Governance: Ticket System
"""
import asyncio
from typing import Dict, Any, Optional, List
from loguru import logger
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class TicketStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"

class Ticket(BaseModel):
    """A request for human approval."""
    id: str
    requester_id: str
    description: str
    context: Dict[str, Any] = Field(default_factory=dict)
    status: TicketStatus = TicketStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    reviewer_id: Optional[str] = None

class TicketSystem:
    """Manages tickets for human-in-the-loop approvals."""
    
    def __init__(self):
        self._tickets: Dict[str, Ticket] = {}
        self._futures: Dict[str, asyncio.Future] = {}

    async def create_ticket(self, requester_id: str, description: str, context: Dict[str, Any]) -> Ticket:
        """Create a new ticket and wait for approval."""
        ticket_id = f"tix_{len(self._tickets) + 1}"
        ticket = Ticket(id=ticket_id, requester_id=requester_id, description=description, context=context)
        self._tickets[ticket_id] = ticket
        
        logger.info(f"New ticket created: {ticket_id} - {description}")
        
        # In a real system, this would notify an admin via a channel
        
        future = asyncio.get_event_loop().create_future()
        self._futures[ticket_id] = future
        
        return await future

    def resolve_ticket(self, ticket_id: str, status: TicketStatus, reviewer_id: str):
        """Resolve a pending ticket."""
        if ticket_id not in self._tickets:
            return False
            
        ticket = self._tickets[ticket_id]
        if ticket.status != TicketStatus.PENDING:
            return False
            
        ticket.status = status
        ticket.resolved_at = datetime.utcnow()
        ticket.reviewer_id = reviewer_id
        
        if ticket_id in self._futures:
            future = self._futures.pop(ticket_id)
            if not future.done():
                future.set_result(ticket)
                
        logger.info(f"Ticket {ticket_id} resolved as {status} by {reviewer_id}")
        return True

    def get_pending_tickets(self) -> List[Ticket]:
        """List all pending tickets."""
        return [t for t in self._tickets.values() if t.status == TicketStatus.PENDING]

# Global ticket system instance
tickets = TicketSystem()
