# ruff: noqa: PLR0913, ERA001, N818, PLC0415
"""Tool & Agent Safety Approval Engine.

Implements:
- Tool risk classification (READ_ONLY, LOW, MEDIUM, HIGH, CRITICAL).
- Human-in-the-loop approval triggers for privileged, destructive, and mutating actions.
- Per-agent tool allowlists and denylists.
- Runaway loop and recursive execution guards with hard turn budgets.
"""

import json
from enum import StrEnum
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.security.audit import AuditEvent, SecurityAuditLogger


class ToolRiskLevel(StrEnum):
    """Risk tier of a tool based on operational impact."""

    READ_ONLY = "read_only"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalStatus(StrEnum):
    """Decision state for a tool execution request."""

    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING_APPROVAL = "pending_approval"


class RunawayLoopDetected(RuntimeError):
    """Raised when an agent triggers an infinite recursion or runaway loop budget."""


class ApprovalDecision(BaseModel):
    """Structured response from the tool safety evaluation."""

    status: ApprovalStatus
    tool_name: str
    agent_id: str
    risk_level: ToolRiskLevel
    ticket_id: str | None = None
    reason: str = ""


class ToolSafetyPolicy(BaseModel):
    """Configurable safety constraints and risk thresholds."""

    require_human_approval_levels: list[ToolRiskLevel] = Field(
        default_factory=lambda: [ToolRiskLevel.HIGH, ToolRiskLevel.CRITICAL]
    )
    agent_allowlists: dict[str, list[str]] = Field(default_factory=dict)
    agent_denylists: dict[str, list[str]] = Field(default_factory=dict)
    max_calls_per_turn: int = 25
    max_duplicate_consecutive_calls: int = 3


class RunawayLoopGuard:
    """Monitors tool calls per turn to prevent runaway loops and infinite recursion."""

    def __init__(
        self,
        max_calls_per_turn: int = 25,
        max_duplicate_consecutive_calls: int = 3,
    ) -> None:
        self.max_calls_per_turn = max_calls_per_turn
        self.max_duplicate_consecutive_calls = max_duplicate_consecutive_calls
        # {turn_id: [tool_name, ...]}
        self._turn_call_counts: dict[str, int] = {}
        # {turn_id: (last_tool, last_args_hash, count)}
        self._turn_consecutive: dict[str, tuple[str, str, int]] = {}

    def _hash_args(self, args: dict[str, Any]) -> str:
        try:
            return json.dumps(args, sort_keys=True, default=str)
        except Exception:
            return str(args)

    def record_and_check(
        self, turn_id: str, tool_name: str, args: dict[str, Any]
    ) -> None:
        """Record a tool call and raise RunawayLoopDetected if safety thresholds are breached."""
        # 1. Check total calls in this turn
        current_count = self._turn_call_counts.get(turn_id, 0) + 1
        self._turn_call_counts[turn_id] = current_count
        if current_count > self.max_calls_per_turn:
            logger.error(
                "RunawayLoopGuard: Turn '{}' exceeded max tool calls ({}/{})",
                turn_id,
                current_count,
                self.max_calls_per_turn,
            )
            raise RunawayLoopDetected(
                f"Runaway loop detected: turn '{turn_id}' exceeded limit of {self.max_calls_per_turn} calls"
            )

        # 2. Check consecutive identical tool invocations
        args_hash = self._hash_args(args)
        last_tool, last_hash, consecutive_count = self._turn_consecutive.get(
            turn_id, ("", "", 0)
        )

        if last_tool == tool_name and last_hash == args_hash:
            consecutive_count += 1
        else:
            consecutive_count = 1

        self._turn_consecutive[turn_id] = (tool_name, args_hash, consecutive_count)

        if consecutive_count >= self.max_duplicate_consecutive_calls:
            logger.error(
                "RunawayLoopGuard: Tool '{}' called {} times consecutively with identical arguments in turn '{}'",
                tool_name,
                consecutive_count,
                turn_id,
            )
            raise RunawayLoopDetected(
                f"Runaway loop detected: '{tool_name}' invoked {consecutive_count} consecutive times with identical parameters"
            )

    def reset_turn(self, turn_id: str) -> None:
        """Reset counters for a finished turn."""
        self._turn_call_counts.pop(turn_id, None)
        self._turn_consecutive.pop(turn_id, None)

    def clear(self) -> None:
        self._turn_call_counts.clear()
        self._turn_consecutive.clear()


class ToolApprovalManager:
    """Evaluates tool execution requests against policies, allowlists, and governance queues."""

    _instance: "ToolApprovalManager | None" = None

    def __init__(self, policy: ToolSafetyPolicy | None = None) -> None:
        self.policy = policy or ToolSafetyPolicy()
        self.loop_guard = RunawayLoopGuard(
            max_calls_per_turn=self.policy.max_calls_per_turn,
            max_duplicate_consecutive_calls=self.policy.max_duplicate_consecutive_calls,
        )
        self._pending_tickets: dict[str, dict[str, Any]] = {}

    @classmethod
    def get_instance(cls) -> "ToolApprovalManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def evaluate_tool_execution(
        self,
        tool_name: str,
        agent_id: str,
        args: dict[str, Any],
        risk_level: ToolRiskLevel = ToolRiskLevel.LOW,
        turn_id: str | None = None,
        bypass_human_check: bool = False,
    ) -> ApprovalDecision:
        """Evaluate if tool execution is authorized, rejected, or requires human approval."""
        # 1. Run runaway loop checks if turn_id is supplied
        if turn_id:
            self.loop_guard.record_and_check(turn_id, tool_name, args)

        # 2. Check per-agent denylist
        denylist = self.policy.agent_denylists.get(agent_id, [])
        if "*" in denylist or tool_name in denylist:
            return ApprovalDecision(
                status=ApprovalStatus.REJECTED,
                tool_name=tool_name,
                agent_id=agent_id,
                risk_level=risk_level,
                reason=f"Tool '{tool_name}' is denylisted for agent '{agent_id}'",
            )

        # 3. Check per-agent allowlist (if configured for this agent)
        if agent_id in self.policy.agent_allowlists:
            allowlist = self.policy.agent_allowlists[agent_id]
            if "*" not in allowlist and tool_name not in allowlist:
                return ApprovalDecision(
                    status=ApprovalStatus.REJECTED,
                    tool_name=tool_name,
                    agent_id=agent_id,
                    risk_level=risk_level,
                    reason=f"Tool '{tool_name}' is not in allowlist for agent '{agent_id}'",
                )

        # 4. Check if human approval is required
        if (
            not bypass_human_check
            and risk_level in self.policy.require_human_approval_levels
        ):
            import uuid

            ticket_id = f"tick_{uuid.uuid4().hex[:12]}"
            self._pending_tickets[ticket_id] = {
                "tool_name": tool_name,
                "agent_id": agent_id,
                "args": args,
                "risk_level": risk_level,
                "status": "pending",
            }

            # Emit audit event for governance review
            audit_logger = SecurityAuditLogger.get_logger()
            audit_logger.log_event(
                AuditEvent(
                    actor=agent_id,
                    action="tool.approval_required",
                    resource_type="tool",
                    resource_id=tool_name,
                    outcome="pending",
                    metadata={
                        "risk_level": risk_level,
                        "ticket_id": ticket_id,
                    },
                )
            )

            return ApprovalDecision(
                status=ApprovalStatus.PENDING_APPROVAL,
                tool_name=tool_name,
                agent_id=agent_id,
                risk_level=risk_level,
                ticket_id=ticket_id,
                reason=f"Tool '{tool_name}' has risk level '{risk_level}' and requires human approval",
            )

        # 5. Default approved
        return ApprovalDecision(
            status=ApprovalStatus.APPROVED,
            tool_name=tool_name,
            agent_id=agent_id,
            risk_level=risk_level,
            reason="Execution policy checks passed",
        )

    def resolve_ticket(
        self, ticket_id: str, approved: bool, reviewer: str = "human_operator"
    ) -> bool:
        """Approve or reject a pending governance ticket."""
        if ticket_id in self._pending_tickets:
            self._pending_tickets[ticket_id]["status"] = (
                "approved" if approved else "rejected"
            )
            audit_logger = SecurityAuditLogger.get_logger()
            audit_logger.log_event(
                AuditEvent(
                    actor=reviewer,
                    action="tool.approval_resolved",
                    resource_type="governance_ticket",
                    resource_id=ticket_id,
                    outcome="success" if approved else "denied",
                    metadata={"approved": approved},
                )
            )
            return True
        return False

    def clear(self) -> None:
        self.loop_guard.clear()
        self._pending_tickets.clear()
