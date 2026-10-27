import asyncio
import logging
from enum import StrEnum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionProposal(BaseModel):
    """
    Represents an action proposed by an agent that requires governance approval.
    """

    action_id: str = Field(..., description="Unique ID for the proposed action.")
    agent_id: str = Field(..., description="The ID of the agent proposing the action.")
    description: str = Field(
        ..., description="Human-readable description of the action."
    )
    risk_level: RiskLevel = Field(
        default=RiskLevel.MEDIUM, description="Assessed risk level."
    )
    cost_estimate: float = Field(default=0.0, description="Estimated cost in USD.")


class GovernanceBoard:
    """
    The 'Board of Directors' for AmberClaw.
    Enforces policies, budget limits, and requires human-in-the-loop for high-risk actions.
    """

    def __init__(
        self,
        require_human_approval_above: RiskLevel = RiskLevel.HIGH,
        max_auto_budget: float = 1.0,
    ) -> None:
        self.require_human_approval_above = require_human_approval_above
        self.max_auto_budget = max_auto_budget
        self._pending_approvals: list[ActionProposal] = []

    def _risk_value(self, level: RiskLevel) -> int:
        return {"low": 1, "medium": 2, "high": 3, "critical": 4}[level.value]

    async def evaluate_proposal(self, proposal: ActionProposal) -> bool:
        """
        Evaluates an action proposal. Returns True if automatically approved,
        False if it requires human intervention or is rejected.
        """
        logger.info(
            f"Evaluating proposal {proposal.action_id} from {proposal.agent_id}: {proposal.description}"
        )

        # Check budget limits
        if proposal.cost_estimate > self.max_auto_budget:
            logger.warning(
                f"Proposal {proposal.action_id} exceeds auto-budget (${proposal.cost_estimate} > ${self.max_auto_budget}). Human approval required."
            )
            self._pending_approvals.append(proposal)

            from amberclaw.governance.tickets import (  # noqa: PLC0415
                TicketStatus,
                tickets,
            )

            created_ticket = await tickets.create_ticket(
                requester_id=proposal.agent_id,
                description=f"Action proposal {proposal.action_id} exceeds auto-budget: {proposal.description} (Estimated cost: ${proposal.cost_estimate})",
                context={
                    "proposal_id": proposal.action_id,
                    "cost_estimate": proposal.cost_estimate,
                    "risk_level": proposal.risk_level.value,
                },
            )

            # Wait for ticket resolution
            resolved_status = TicketStatus.PENDING
            for _ in range(50):
                await asyncio.sleep(0.05)
                current_ticket = tickets.get_ticket(created_ticket.id)
                if current_ticket and current_ticket.status != TicketStatus.PENDING:
                    resolved_status = current_ticket.status
                    break

            if proposal in self._pending_approvals:
                self._pending_approvals.remove(proposal)
            return resolved_status == TicketStatus.APPROVED

        # Check risk limits
        if self._risk_value(proposal.risk_level) >= self._risk_value(
            self.require_human_approval_above
        ):
            logger.warning(
                f"Proposal {proposal.action_id} is {proposal.risk_level.value} risk. Human approval required."
            )
            self._pending_approvals.append(proposal)

            from amberclaw.governance.tickets import (  # noqa: PLC0415
                TicketStatus,
                tickets,
            )

            created_ticket = await tickets.create_ticket(
                requester_id=proposal.agent_id,
                description=f"Action proposal {proposal.action_id} requires high risk approval: {proposal.description} (Risk level: {proposal.risk_level.value})",
                context={
                    "proposal_id": proposal.action_id,
                    "cost_estimate": proposal.cost_estimate,
                    "risk_level": proposal.risk_level.value,
                },
            )

            # Wait for ticket resolution
            resolved_status = TicketStatus.PENDING
            for _ in range(50):
                await asyncio.sleep(0.05)
                current_ticket = tickets.get_ticket(created_ticket.id)
                if current_ticket and current_ticket.status != TicketStatus.PENDING:
                    resolved_status = current_ticket.status
                    break

            if proposal in self._pending_approvals:
                self._pending_approvals.remove(proposal)
            return resolved_status == TicketStatus.APPROVED

        logger.info(f"Proposal {proposal.action_id} automatically approved.")
        return True

    def get_pending_approvals(self) -> list[ActionProposal]:
        """Returns the list of actions waiting for human approval."""
        return self._pending_approvals

    def approve_action(self, action_id: str) -> bool:
        """Human approval of a pending action."""
        for proposal in self._pending_approvals:
            if proposal.action_id == action_id:
                from amberclaw.governance.tickets import (  # noqa: PLC0415
                    TicketStatus,
                    tickets,
                )

                for ticket in tickets.get_pending_tickets():
                    if ticket.context.get("proposal_id") == action_id:
                        tickets.resolve_ticket(
                            ticket.id,
                            TicketStatus.APPROVED,
                            reviewer_id="board_operator",
                        )
                        return True

                self._pending_approvals.remove(proposal)
                logger.info(f"Human explicitly approved proposal {action_id} directly.")
                return True
        logger.error(f"Could not find pending proposal {action_id} to approve.")
        return False
