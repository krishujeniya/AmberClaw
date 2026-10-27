"""Ticket lease management and distributed checkout lock primitives."""

import time
import uuid

from loguru import logger
from pydantic import BaseModel, Field


class TicketCheckout(BaseModel):
    """Lease claim record for a ticket under active processing."""

    checkout_id: str = Field(
        default_factory=lambda: f"CHK-{uuid.uuid4().hex[:8].upper()}"
    )
    ticket_id: str = Field(..., description="Target ticket ID")
    claimed_by: str = Field(
        ..., description="Agent or operator claiming exclusive work lock"
    )
    claimed_at: float = Field(default_factory=time.time)
    expires_at: float = Field(..., description="Unix timestamp when lease expires")
    is_active: bool = Field(default=True)


class CheckoutManager:
    """Manages exclusive lease-based checkouts of tickets to prevent concurrent processing races."""

    def __init__(self) -> None:
        self._checkouts: dict[str, TicketCheckout] = {}  # ticket_id -> TicketCheckout

    def is_claimed(self, ticket_id: str) -> bool:
        """Check if a ticket is currently actively claimed under an unexpired lease."""
        chk = self._checkouts.get(ticket_id)
        if not chk or not chk.is_active:
            return False
        if time.time() >= chk.expires_at:
            chk.is_active = False
            return False
        return True

    def get_active_checkout(self, ticket_id: str) -> TicketCheckout | None:
        """Retrieve active checkout record if still valid."""
        if self.is_claimed(ticket_id):
            return self._checkouts.get(ticket_id)
        return None

    def claim_ticket(
        self,
        ticket_id: str,
        claimed_by: str,
        lease_seconds: float = 300.0,
    ) -> TicketCheckout:
        """Attempt to claim an exclusive lease on a ticket."""
        now = time.time()
        if self.is_claimed(ticket_id):
            existing = self._checkouts[ticket_id]
            if existing.claimed_by != claimed_by:
                raise RuntimeError(
                    f"Ticket '{ticket_id}' is already claimed by '{existing.claimed_by}' until {existing.expires_at}"
                )

        checkout = TicketCheckout(
            ticket_id=ticket_id,
            claimed_by=claimed_by,
            claimed_at=now,
            expires_at=now + lease_seconds,
            is_active=True,
        )
        self._checkouts[ticket_id] = checkout
        logger.info(
            "Ticket [{}] claimed by '{}' for {:.0f}s (lease id: {})",
            ticket_id,
            claimed_by,
            lease_seconds,
            checkout.checkout_id,
        )
        return checkout

    def renew_lease(
        self,
        ticket_id: str,
        claimed_by: str,
        extend_seconds: float = 300.0,
    ) -> TicketCheckout:
        """Extend the expiry of an existing active checkout lease."""
        if not self.is_claimed(ticket_id):
            raise KeyError(f"Ticket '{ticket_id}' has no active claim to renew.")

        chk = self._checkouts[ticket_id]
        if chk.claimed_by != claimed_by:
            raise PermissionError(f"Cannot renew lease claimed by '{chk.claimed_by}'.")

        chk.expires_at = time.time() + extend_seconds
        logger.debug(
            "Lease on ticket [{}] renewed by '{}' for {:.0f}s",
            ticket_id,
            claimed_by,
            extend_seconds,
        )
        return chk

    def release_ticket(self, ticket_id: str, claimed_by: str) -> bool:
        """Explicitly release lease lock on a ticket."""
        chk = self._checkouts.get(ticket_id)
        if not chk or not chk.is_active:
            return False

        if chk.claimed_by != claimed_by:
            raise PermissionError(f"Cannot release lease owned by '{chk.claimed_by}'.")

        chk.is_active = False
        logger.info("Ticket [{}] released by '{}'", ticket_id, claimed_by)
        return True
