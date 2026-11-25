"""Ticket inbox and triage queue management for operational work streams."""

import time

from loguru import logger
from pydantic import BaseModel

from amberclaw.tickets.checkout import CheckoutManager
from amberclaw.tickets.issue import Issue, IssueManager, IssueSeverity, IssueStatus


class InboxFilter(BaseModel):
    """Filter parameters for querying operational ticket inboxes."""

    assignee: str | None = None
    severity: IssueSeverity | None = None
    status: IssueStatus | None = None
    tag: str | None = None
    unassigned_only: bool = False
    include_claimed: bool = True


class TicketInbox:
    """Triage view coordinating unassigned work, priority sorting, and SLA monitoring."""

    def __init__(
        self,
        issue_manager: IssueManager | None = None,
        checkout_manager: CheckoutManager | None = None,
    ) -> None:
        self.issue_manager = issue_manager or IssueManager()
        self.checkout_manager = checkout_manager or CheckoutManager()

    def get_triage_queue(self, inbox_filter: InboxFilter | None = None) -> list[Issue]:
        """Fetch prioritized work queue according to operational rules."""
        f = inbox_filter or InboxFilter()
        all_issues = self.issue_manager.list_issues(
            status=f.status,
            severity=f.severity,
            assignee=f.assignee,
            tag=f.tag,
        )

        results: list[Issue] = []
        for issue in all_issues:
            if f.unassigned_only and issue.assignee:
                continue
            if not f.include_claimed and self.checkout_manager.is_claimed(
                issue.issue_id
            ):
                continue
            results.append(issue)

        # Sort priority: CRITICAL (0), MAJOR (1), MINOR (2), TRIVIAL (3)
        severity_rank = {
            IssueSeverity.CRITICAL: 0,
            IssueSeverity.MAJOR: 1,
            IssueSeverity.MINOR: 2,
            IssueSeverity.TRIVIAL: 3,
        }

        results.sort(
            key=lambda x: (
                severity_rank.get(x.severity, 4),
                x.created_at,
            )
        )
        return results

    def get_unassigned_issues(self) -> list[Issue]:
        """Convenience method to retrieve unassigned open or triaged issues."""
        return self.get_triage_queue(InboxFilter(unassigned_only=True))

    def get_assigned_issues(self, assignee: str) -> list[Issue]:
        """Convenience method to retrieve all issues assigned to a specific worker."""
        return self.get_triage_queue(InboxFilter(assignee=assignee))

    def detect_sla_breaches(self, max_age_seconds: float = 3600.0) -> list[Issue]:
        """Identify open or triaged issues that have breached the maximum resolution threshold."""
        now = time.time()
        active_statuses = (
            IssueStatus.OPEN,
            IssueStatus.TRIAGED,
            IssueStatus.IN_PROGRESS,
            IssueStatus.BLOCKED,
        )
        breaches: list[Issue] = []

        for issue in self.issue_manager.list_issues():
            if (
                issue.status in active_statuses
                and (now - issue.created_at) > max_age_seconds
            ):
                breaches.append(issue)

        if breaches:
            logger.warning("Detected {} operational SLA breaches", len(breaches))
        return breaches
