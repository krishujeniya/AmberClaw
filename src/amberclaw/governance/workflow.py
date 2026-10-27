"""Multi-stage approval workflow and voting engine for governance decisions."""

import time
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class WorkflowStage(StrEnum):
    SUBMITTED = "submitted"
    AUTOMATED_CHECKS = "automated_checks"
    HUMAN_REVIEW = "human_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ApprovalVote(BaseModel):
    """A vote cast by a human reviewer or safety evaluator."""

    reviewer_id: str
    approved: bool
    comments: str = ""
    timestamp: float = Field(default_factory=time.time)


class ApprovalRequest(BaseModel):
    """A governed multi-stage approval workflow instance."""

    request_id: str = Field(default_factory=lambda: f"REQ-{uuid.uuid4().hex[:8].upper()}")
    requester_id: str
    title: str
    description: str = ""
    stage: WorkflowStage = WorkflowStage.SUBMITTED
    required_approvals: int = 1
    votes: list[ApprovalVote] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    expires_at: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def approval_count(self) -> int:
        return sum(1 for v in self.votes if v.approved)

    @property
    def rejection_count(self) -> int:
        return sum(1 for v in self.votes if not v.approved)

    @property
    def is_finalized(self) -> bool:
        return self.stage in {WorkflowStage.APPROVED, WorkflowStage.REJECTED, WorkflowStage.EXPIRED}


class WorkflowEngine:
    """Orchestrates submission, automated stage evaluation, and human consensus voting."""

    def __init__(self) -> None:
        self._requests: dict[str, ApprovalRequest] = {}

    def submit_request(
        self,
        requester_id: str,
        title: str,
        description: str = "",
        required_approvals: int = 1,
        auto_pass_checks: bool = True,
    ) -> ApprovalRequest:
        """Create and start a new approval workflow request."""
        now = time.time()
        ttl_seconds = 86400.0
        req = ApprovalRequest(
            requester_id=requester_id,
            title=title,
            description=description,
            required_approvals=required_approvals,
            stage=WorkflowStage.AUTOMATED_CHECKS if auto_pass_checks else WorkflowStage.SUBMITTED,
            created_at=now,
            expires_at=now + ttl_seconds,
        )

        if auto_pass_checks:
            req.stage = WorkflowStage.HUMAN_REVIEW

        self._requests[req.request_id] = req
        return req

    def get_request(self, request_id: str) -> ApprovalRequest | None:
        """Retrieve request by ID."""
        return self._requests.get(request_id)

    def cast_vote(
        self,
        request_id: str,
        reviewer_id: str,
        approved: bool,
        comments: str = "",
    ) -> ApprovalRequest:
        """Record reviewer decision and evaluate transition to APPROVED or REJECTED."""
        req = self._requests.get(request_id)
        if not req:
            raise KeyError(f"Approval request {request_id} not found.")

        if req.is_finalized:
            raise ValueError(f"Cannot vote on finalized request in stage {req.stage}.")

        # Check expiration
        if req.expires_at and time.time() > req.expires_at:
            req.stage = WorkflowStage.EXPIRED
            return req

        vote = ApprovalVote(reviewer_id=reviewer_id, approved=approved, comments=comments)
        req.votes.append(vote)

        if not approved:
            req.stage = WorkflowStage.REJECTED
        elif req.approval_count >= req.required_approvals:
            req.stage = WorkflowStage.APPROVED

        return req

    def list_pending(self) -> list[ApprovalRequest]:
        """List all requests awaiting decision."""
        return [r for r in self._requests.values() if not r.is_finalized]
