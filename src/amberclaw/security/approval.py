# ruff: noqa: PLR0913, ERA001, N818, PLR0911, PLR0912, ARG001
"""Tool & Agent Safety Approval Engine.

Implements:
- Tool risk classification (READ_ONLY, LOW, MEDIUM, HIGH, CRITICAL).
- Human-in-the-loop approval triggers for privileged, destructive, and mutating actions.
- Per-agent tool allowlists and denylists.
- Runaway loop and recursive execution guards with hard turn budgets.
"""

import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
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
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class RunawayLoopDetected(RuntimeError):
    """Raised when an agent triggers an infinite recursion or runaway loop budget."""


class ApprovalTicket(BaseModel):
    """Immutable governance ticket for human-in-the-loop tool execution."""

    ticket_id: str
    actor: str
    tenant_id: str = "default"
    tool_name: str
    action_type: str = "tool_execution"
    action_version: str = "1.0.0"
    args: dict[str, Any] = Field(default_factory=dict)
    args_hash: str
    destination: str = "local"
    scope: str = "tool:execute"
    estimated_cost_usd: float = 0.0
    risk_level: ToolRiskLevel = ToolRiskLevel.MEDIUM
    status: ApprovalStatus = ApprovalStatus.PENDING_APPROVAL
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime
    resolved_at: datetime | None = None
    reviewer_id: str | None = None
    notes: str | None = None
    consumed: bool = False
    consumed_at: datetime | None = None
    consumed_by: str | None = None


class ApprovalDecision(BaseModel):
    """Structured response from the tool safety evaluation."""

    status: ApprovalStatus
    tool_name: str
    agent_id: str
    risk_level: ToolRiskLevel
    ticket_id: str | None = None
    reason: str = ""
    ticket: ApprovalTicket | None = None


class ToolSafetyPolicy(BaseModel):
    """Configurable safety constraints and risk thresholds."""

    require_human_approval_levels: list[ToolRiskLevel] = Field(
        default_factory=lambda: [ToolRiskLevel.HIGH, ToolRiskLevel.CRITICAL]
    )
    agent_allowlists: dict[str, list[str]] = Field(default_factory=dict)
    agent_denylists: dict[str, list[str]] = Field(default_factory=dict)
    max_calls_per_turn: int = 25
    max_duplicate_consecutive_calls: int = 3
    ticket_ttl_seconds: int = 900


def compute_arguments_hash(args: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash over invocation arguments, omitting ticket metadata."""
    filtered = {
        k: v for k, v in args.items() if k not in ("approval_ticket_id", "ticket_id")
    }
    serialized = json.dumps(
        filtered, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def infer_destination(tool_name: str, args: dict[str, Any]) -> str:
    """Extract target destination (host, path, URL, shell) from arguments."""
    for key in (
        "destination",
        "url",
        "host",
        "endpoint",
        "path",
        "file_path",
        "target",
        "db",
        "cwd",
    ):
        val = args.get(key)
        if val:
            return str(val)
    if "command" in args:
        return "local_shell"
    return "local"


def infer_scope(tool_name: str, args: dict[str, Any]) -> str:
    """Determine the least-privilege permission scope required for the action."""
    scope_val = args.get("scope")
    if scope_val:
        return str(scope_val)
    if tool_name in ("bash", "shell", "exec"):
        cmd_prefix = (
            str(args.get("command", "")).split()[0]
            if args.get("command")
            else "exec"
        )
        return f"shell:{cmd_prefix}"
    if tool_name in ("write_file", "edit_file", "delete_file", "delete_database"):
        target = args.get("path", args.get("file_path", args.get("db", "*")))
        return f"fs:write:{target}"
    if tool_name in ("read_file", "list_dir"):
        target = args.get("path", args.get("file_path", "*"))
        return f"fs:read:{target}"
    if tool_name in ("http_request", "fetch_url", "api_call"):
        return f"net:egress:{args.get('url', args.get('host', '*'))}"
    return f"tool:{tool_name}"


def estimate_action_cost(tool_name: str, args: dict[str, Any]) -> float:
    """Provide a conservative upper-bound cost estimate for the action in USD."""
    if "estimated_cost_usd" in args:
        try:
            return float(args["estimated_cost_usd"])
        except (ValueError, TypeError):
            pass
    if tool_name in ("llm_call", "model_inference"):
        return 0.02
    if tool_name in ("web_scrape", "browser_run"):
        return 0.005
    return 0.001


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
        self._tickets: dict[str, ApprovalTicket] = {}
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
        tenant_id: str = "default",
        action_version: str = "1.0.0",
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

        # 4. Check if an approved ticket was provided for execution
        ticket_id = args.get("approval_ticket_id") or args.get("ticket_id")
        if ticket_id:
            ticket = self._tickets.get(ticket_id)
            if not ticket:
                # Check legacy dictionary if any
                legacy = self._pending_tickets.get(ticket_id)
                if not legacy or legacy.get("status") != "approved":
                    return ApprovalDecision(
                        status=ApprovalStatus.REJECTED,
                        tool_name=tool_name,
                        agent_id=agent_id,
                        risk_level=risk_level,
                        ticket_id=ticket_id,
                        reason=f"Approval ticket '{ticket_id}' not found or not approved",
                    )
                return ApprovalDecision(
                    status=ApprovalStatus.APPROVED,
                    tool_name=tool_name,
                    agent_id=agent_id,
                    risk_level=risk_level,
                    ticket_id=ticket_id,
                    reason="Pre-approved legacy ticket verified",
                )

            # Ticket exists. Check status
            if ticket.status == ApprovalStatus.REJECTED:
                return ApprovalDecision(
                    status=ApprovalStatus.REJECTED,
                    tool_name=tool_name,
                    agent_id=agent_id,
                    risk_level=risk_level,
                    ticket_id=ticket_id,
                    ticket=ticket,
                    reason=f"Approval ticket '{ticket_id}' was rejected by reviewer",
                )
            if ticket.status == ApprovalStatus.CANCELLED:
                return ApprovalDecision(
                    status=ApprovalStatus.REJECTED,
                    tool_name=tool_name,
                    agent_id=agent_id,
                    risk_level=risk_level,
                    ticket_id=ticket_id,
                    ticket=ticket,
                    reason=f"Approval ticket '{ticket_id}' was cancelled",
                )
            if ticket.status == ApprovalStatus.PENDING_APPROVAL:
                return ApprovalDecision(
                    status=ApprovalStatus.PENDING_APPROVAL,
                    tool_name=tool_name,
                    agent_id=agent_id,
                    risk_level=risk_level,
                    ticket_id=ticket_id,
                    ticket=ticket,
                    reason=f"Approval ticket '{ticket_id}' is pending review",
                )

            # Check expiry
            now = datetime.now(UTC)
            if now > ticket.expires_at:
                ticket.status = ApprovalStatus.EXPIRED
                if ticket_id in self._pending_tickets:
                    self._pending_tickets[ticket_id]["status"] = "expired"
                return ApprovalDecision(
                    status=ApprovalStatus.REJECTED,
                    tool_name=tool_name,
                    agent_id=agent_id,
                    risk_level=risk_level,
                    ticket_id=ticket_id,
                    ticket=ticket,
                    reason=f"Approval ticket '{ticket_id}' has expired (expired at {ticket.expires_at.isoformat()})",
                )

            # Check replay prevention (single-use enforcement)
            if ticket.consumed:
                return ApprovalDecision(
                    status=ApprovalStatus.REJECTED,
                    tool_name=tool_name,
                    agent_id=agent_id,
                    risk_level=risk_level,
                    ticket_id=ticket_id,
                    ticket=ticket,
                    reason=f"Approval ticket '{ticket_id}' already consumed at {ticket.consumed_at.isoformat() if ticket.consumed_at else 'prior'} by '{ticket.consumed_by}' (replay attack prevented)",
                )

            # Check argument tampering
            current_hash = compute_arguments_hash(args)
            if current_hash != ticket.args_hash:
                return ApprovalDecision(
                    status=ApprovalStatus.REJECTED,
                    tool_name=tool_name,
                    agent_id=agent_id,
                    risk_level=risk_level,
                    ticket_id=ticket_id,
                    ticket=ticket,
                    reason=f"Arguments modified after approval (tampering detected: expected hash '{ticket.args_hash}', got '{current_hash}')",
                )

            # Check identity binding
            if agent_id != ticket.actor:
                return ApprovalDecision(
                    status=ApprovalStatus.REJECTED,
                    tool_name=tool_name,
                    agent_id=agent_id,
                    risk_level=risk_level,
                    ticket_id=ticket_id,
                    ticket=ticket,
                    reason=f"Requester identity mismatch: ticket actor is '{ticket.actor}', caller is '{agent_id}'",
                )
            if tenant_id and ticket.tenant_id and tenant_id != ticket.tenant_id:
                return ApprovalDecision(
                    status=ApprovalStatus.REJECTED,
                    tool_name=tool_name,
                    agent_id=agent_id,
                    risk_level=risk_level,
                    ticket_id=ticket_id,
                    ticket=ticket,
                    reason=f"Tenant identity mismatch: ticket tenant is '{ticket.tenant_id}', caller is '{tenant_id}'",
                )

            # Check tool name
            if tool_name != ticket.tool_name:
                return ApprovalDecision(
                    status=ApprovalStatus.REJECTED,
                    tool_name=tool_name,
                    agent_id=agent_id,
                    risk_level=risk_level,
                    ticket_id=ticket_id,
                    ticket=ticket,
                    reason=f"Tool name mismatch: ticket approved for '{ticket.tool_name}', caller invoked '{tool_name}'",
                )

            # Single-use consumption
            ticket.consumed = True
            ticket.consumed_at = now
            ticket.consumed_by = agent_id

            # Audit event
            audit_logger = SecurityAuditLogger.get_logger()
            audit_logger.log_event(
                AuditEvent(
                    actor=agent_id,
                    action="tool.approval_consumed",
                    resource_type="governance_ticket",
                    resource_id=ticket_id,
                    outcome="success",
                    metadata={
                        "tool_name": tool_name,
                        "args_hash": ticket.args_hash,
                        "tenant_id": ticket.tenant_id,
                    },
                )
            )

            return ApprovalDecision(
                status=ApprovalStatus.APPROVED,
                tool_name=tool_name,
                agent_id=agent_id,
                risk_level=risk_level,
                ticket_id=ticket_id,
                ticket=ticket,
                reason="Pre-approved governance ticket verified and consumed",
            )

        # 5. Check if human approval is required
        if (
            not bypass_human_check
            and risk_level in self.policy.require_human_approval_levels
        ):
            ticket_id = f"tick_{uuid.uuid4().hex[:12]}"
            args_hash = compute_arguments_hash(args)
            now = datetime.now(UTC)
            expires_at = now + timedelta(seconds=self.policy.ticket_ttl_seconds)

            ticket = ApprovalTicket(
                ticket_id=ticket_id,
                actor=agent_id,
                tenant_id=tenant_id,
                tool_name=tool_name,
                action_type="tool_execution",
                action_version=action_version,
                args=args,
                args_hash=args_hash,
                destination=infer_destination(tool_name, args),
                scope=infer_scope(tool_name, args),
                estimated_cost_usd=estimate_action_cost(tool_name, args),
                risk_level=risk_level,
                status=ApprovalStatus.PENDING_APPROVAL,
                created_at=now,
                expires_at=expires_at,
            )
            self._tickets[ticket_id] = ticket
            self._pending_tickets[ticket_id] = {
                "tool_name": tool_name,
                "agent_id": agent_id,
                "args": args,
                "risk_level": risk_level,
                "status": "pending",
                "args_hash": args_hash,
                "destination": ticket.destination,
                "scope": ticket.scope,
                "estimated_cost_usd": ticket.estimated_cost_usd,
                "expires_at": expires_at.isoformat(),
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
                        "args_hash": args_hash,
                        "destination": ticket.destination,
                        "scope": ticket.scope,
                        "estimated_cost_usd": ticket.estimated_cost_usd,
                        "expires_at": expires_at.isoformat(),
                    },
                )
            )

            return ApprovalDecision(
                status=ApprovalStatus.PENDING_APPROVAL,
                tool_name=tool_name,
                agent_id=agent_id,
                risk_level=risk_level,
                ticket_id=ticket_id,
                ticket=ticket,
                reason=f"Tool '{tool_name}' has risk level '{risk_level}' and requires human approval",
            )

        # 6. Default approved
        return ApprovalDecision(
            status=ApprovalStatus.APPROVED,
            tool_name=tool_name,
            agent_id=agent_id,
            risk_level=risk_level,
            reason="Execution policy checks passed",
        )

    def request_approval(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        requester_id: str = "agent",
        tenant_id: str = "default",
        risk_level: ToolRiskLevel = ToolRiskLevel.HIGH,
    ) -> ApprovalTicket:
        """Create and register an explicit pending approval ticket."""
        ticket_id = f"tkt_{secrets.token_hex(8)}"
        args_hash = compute_arguments_hash(parameters)
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=self.policy.ticket_ttl_seconds)

        ticket = ApprovalTicket(
            ticket_id=ticket_id,
            actor=requester_id,
            tenant_id=tenant_id,
            tool_name=tool_name,
            action_type="tool_execution",
            action_version="1.0.0",
            args=parameters,
            args_hash=args_hash,
            destination=infer_destination(tool_name, parameters),
            scope=infer_scope(tool_name, parameters),
            estimated_cost_usd=estimate_action_cost(tool_name, parameters),
            risk_level=risk_level,
            status=ApprovalStatus.PENDING_APPROVAL,
            created_at=now,
            expires_at=expires_at,
        )
        self._tickets[ticket_id] = ticket
        self._pending_tickets[ticket_id] = {
            "tool_name": tool_name,
            "agent_id": requester_id,
            "args": parameters,
            "risk_level": risk_level,
            "status": "pending",
            "args_hash": args_hash,
            "destination": ticket.destination,
            "scope": ticket.scope,
            "estimated_cost_usd": ticket.estimated_cost_usd,
            "expires_at": expires_at.isoformat(),
        }
        return ticket

    def get_ticket(self, ticket_id: str) -> ApprovalTicket | None:
        """Retrieve an approval ticket by its identifier."""
        return self._tickets.get(ticket_id)

    def list_tickets(
        self, status: ApprovalStatus | None = None
    ) -> list[ApprovalTicket]:
        """List all tickets with optional status filtering, ordered newest first."""
        all_t = list(self._tickets.values())
        if status is not None:
            all_t = [t for t in all_t if t.status == status]
        return sorted(all_t, key=lambda t: t.created_at, reverse=True)

    def resolve_ticket(
        self,
        ticket_id: str,
        approved: bool,
        reviewer: str = "human_operator",
        notes: str = "",
    ) -> bool:
        """Approve or reject a pending governance ticket."""
        ticket = self._tickets.get(ticket_id)
        if ticket:
            if ticket.consumed or ticket.status in (
                ApprovalStatus.EXPIRED,
                ApprovalStatus.CANCELLED,
            ):
                return False
            now = datetime.now(UTC)
            if now > ticket.expires_at:
                ticket.status = ApprovalStatus.EXPIRED
                return False

            ticket.status = (
                ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
            )
            ticket.resolved_at = now
            ticket.reviewer_id = reviewer
            ticket.notes = notes

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
                    metadata={"approved": approved, "notes": notes},
                )
            )
            return True

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

    def cancel_ticket(
        self,
        ticket_id: str,
        reason: str = "Cancelled by requester",
        actor: str = "requester",
    ) -> bool:
        """Cancel a pending approval request."""
        ticket = self._tickets.get(ticket_id)
        if ticket:
            if ticket.consumed:
                return False
            ticket.status = ApprovalStatus.CANCELLED
            ticket.notes = reason
            if ticket_id in self._pending_tickets:
                self._pending_tickets[ticket_id]["status"] = "cancelled"

            audit_logger = SecurityAuditLogger.get_logger()
            audit_logger.log_event(
                AuditEvent(
                    actor=actor,
                    action="tool.approval_cancelled",
                    resource_type="governance_ticket",
                    resource_id=ticket_id,
                    outcome="cancelled",
                    metadata={"reason": reason},
                )
            )
            return True

        if ticket_id in self._pending_tickets:
            self._pending_tickets[ticket_id]["status"] = "cancelled"
            return True
        return False

    def clear(self) -> None:
        self.loop_guard.clear()
        self._tickets.clear()
        self._pending_tickets.clear()
