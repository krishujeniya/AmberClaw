"""AmberClaw governance subsystem: Board, Policies, Multi-Stage Workflows, Audit, and Rollbacks."""

from pydantic import BaseModel, Field

from amberclaw.governance.audit import (
    AuditAction,
    AuditLogger,
    AuditQuery,
    AuditRecord,
    audit_logger,
)
from amberclaw.governance.board import (
    ActionProposal,
    GovernanceBoard,
    RiskLevel,
)
from amberclaw.governance.policies import (
    EnforcementAction,
    PolicyEngine,
    PolicyEvaluationResult,
    PolicyRule,
)
from amberclaw.governance.rollback import (
    GovernanceRollbackManager,
    RollbackPlan,
    RollbackStatus,
    RollbackStep,
)
from amberclaw.governance.tickets import (
    Ticket,
    TicketPriority,
    TicketStatus,
    TicketSystem,
    tickets,
)
from amberclaw.governance.workflow import (
    ApprovalRequest,
    ApprovalVote,
    WorkflowEngine,
    WorkflowStage,
)


class GovernanceModuleConfig(BaseModel):
    """Configuration for the amberclaw.governance module."""

    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = [
    "ActionProposal",
    "ApprovalRequest",
    "ApprovalVote",
    "AuditAction",
    "AuditLogger",
    "AuditQuery",
    "AuditRecord",
    "EnforcementAction",
    "GovernanceBoard",
    "GovernanceModuleConfig",
    "GovernanceRollbackManager",
    "PolicyEngine",
    "PolicyEvaluationResult",
    "PolicyRule",
    "RiskLevel",
    "RollbackPlan",
    "RollbackStatus",
    "RollbackStep",
    "Ticket",
    "TicketPriority",
    "TicketStatus",
    "TicketSystem",
    "WorkflowEngine",
    "WorkflowStage",
    "audit_logger",
    "tickets",
]
