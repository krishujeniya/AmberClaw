"""Issue models, status workflows, and issue tracking management."""

import time
import uuid
from enum import StrEnum
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


class IssueStatus(StrEnum):
    """Lifecycle states of an operational issue or ticket."""

    OPEN = "open"
    TRIAGED = "triaged"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IssueSeverity(StrEnum):
    """Operational urgency and impact levels."""

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    TRIVIAL = "trivial"


class Issue(BaseModel):
    """Structured work item representation for AmberClaw operations."""

    issue_id: str = Field(
        default_factory=lambda: f"ISSUE-{uuid.uuid4().hex[:8].upper()}"
    )
    title: str = Field(..., description="Brief summary of the issue")
    description: str = Field(..., description="Detailed context or error trace")
    status: IssueStatus = Field(default=IssueStatus.OPEN)
    severity: IssueSeverity = Field(default=IssueSeverity.MINOR)
    assignee: str | None = Field(
        default=None, description="Assigned operator or agent ID"
    )
    reporter: str = Field(default="system", description="Reporter identity")
    tags: list[str] = Field(default_factory=list, description="Categorization labels")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary context data"
    )
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    resolved_at: float | None = None


class IssueManager:
    """Manages creation, filtering, assignment, and state transitions of operational issues."""

    def __init__(self) -> None:
        self._issues: dict[str, Issue] = {}

    def create_issue(  # noqa: PLR0913
        self,
        title: str,
        description: str,
        severity: IssueSeverity = IssueSeverity.MINOR,
        reporter: str = "system",
        assignee: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Issue:
        """Create and record a new issue."""
        issue = Issue(
            title=title,
            description=description,
            severity=severity,
            reporter=reporter,
            assignee=assignee,
            tags=tags or [],
            metadata=metadata or {},
        )
        self._issues[issue.issue_id] = issue
        logger.info(
            "Created issue [{}] '{}' (severity: {})",
            issue.issue_id,
            issue.title,
            severity.value,
        )
        return issue

    def get_issue(self, issue_id: str) -> Issue | None:
        """Fetch an issue by its ID."""
        return self._issues.get(issue_id)

    def update_status(
        self,
        issue_id: str,
        status: IssueStatus,
    ) -> Issue:
        """Transition the status of an issue."""
        issue = self.get_issue(issue_id)
        if not issue:
            raise KeyError(f"Issue '{issue_id}' not found.")

        old_status = issue.status
        issue.status = status
        issue.updated_at = time.time()

        if (
            status in (IssueStatus.RESOLVED, IssueStatus.CLOSED)
            and not issue.resolved_at
        ):
            issue.resolved_at = time.time()
        elif status not in (IssueStatus.RESOLVED, IssueStatus.CLOSED):
            issue.resolved_at = None

        logger.info(
            "Issue [{}] transitioned from {} to {}",
            issue_id,
            old_status.value,
            status.value,
        )
        return issue

    def assign(self, issue_id: str, assignee: str | None) -> Issue:
        """Assign or unassign an issue to an agent or operator."""
        issue = self.get_issue(issue_id)
        if not issue:
            raise KeyError(f"Issue '{issue_id}' not found.")

        issue.assignee = assignee
        issue.updated_at = time.time()
        if assignee and issue.status == IssueStatus.OPEN:
            issue.status = IssueStatus.IN_PROGRESS
        logger.info("Issue [{}] assigned to '{}'", issue_id, assignee)
        return issue

    def list_issues(
        self,
        status: IssueStatus | None = None,
        severity: IssueSeverity | None = None,
        assignee: str | None = None,
        tag: str | None = None,
    ) -> list[Issue]:
        """Query issues by status, severity, assignee, or tag."""
        results = list(self._issues.values())

        if status is not None:
            results = [i for i in results if i.status == status]
        if severity is not None:
            results = [i for i in results if i.severity == severity]
        if assignee is not None:
            results = [i for i in results if i.assignee == assignee]
        if tag is not None:
            results = [i for i in results if tag in i.tags]

        return sorted(results, key=lambda x: x.created_at, reverse=True)
