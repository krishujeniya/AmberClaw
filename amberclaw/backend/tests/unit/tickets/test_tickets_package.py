# ruff: noqa: PLR2004
"""Unit tests for amberclaw.tickets package (issues, comments, attachments, checkout, inbox)."""

import time
from pathlib import Path

import pytest

from amberclaw.tickets.attachments import AttachmentStore
from amberclaw.tickets.checkout import CheckoutManager
from amberclaw.tickets.comments import CommentManager
from amberclaw.tickets.inbox import InboxFilter, TicketInbox
from amberclaw.tickets.issue import IssueManager, IssueSeverity, IssueStatus

# ==============================================================================
# IssueManager Tests
# ==============================================================================


def test_issue_lifecycle():
    mgr = IssueManager()

    issue = mgr.create_issue(
        title="High Memory Usage in Worker 2",
        description="OOM warning observed on node 2",
        severity=IssueSeverity.MAJOR,
        reporter="monitoring-daemon",
        tags=["node2", "oom"],
    )
    assert issue.issue_id.startswith("ISSUE-")
    assert issue.status == IssueStatus.OPEN
    assert issue.severity == IssueSeverity.MAJOR

    # Assign
    mgr.assign(issue.issue_id, "operator-bob")
    updated = mgr.get_issue(issue.issue_id)
    assert updated is not None
    assert updated.assignee == "operator-bob"
    assert updated.status == IssueStatus.IN_PROGRESS

    # Resolve
    resolved = mgr.update_status(issue.issue_id, IssueStatus.RESOLVED)
    assert resolved.status == IssueStatus.RESOLVED
    assert resolved.resolved_at is not None

    # Filter
    all_resolved = mgr.list_issues(status=IssueStatus.RESOLVED)
    assert len(all_resolved) == 1
    assert all_resolved[0].issue_id == issue.issue_id

    tag_matches = mgr.list_issues(tag="oom")
    assert len(tag_matches) == 1


# ==============================================================================
# CommentManager Tests
# ==============================================================================


def test_comments():
    mgr = CommentManager()
    issue_id = "ISSUE-TEST1"

    c1 = mgr.add_comment(issue_id, "alice", "Investigating logs.")
    c2 = mgr.add_comment(
        issue_id, "bob", "Internal node metric: CPU 99%", is_internal=True
    )

    comments = mgr.get_comments(issue_id, include_internal=True)
    assert len(comments) == 2

    public_only = mgr.get_comments(issue_id, include_internal=False)
    assert len(public_only) == 1
    assert public_only[0].comment_id == c1.comment_id

    # Delete
    assert mgr.delete_comment(issue_id, c2.comment_id) is True
    assert len(mgr.get_comments(issue_id)) == 1


# ==============================================================================
# AttachmentStore Tests
# ==============================================================================


def test_attachments(tmp_path: Path):
    store = AttachmentStore(storage_dir=tmp_path / "attachments")
    issue_id = "ISSUE-ATT1"

    payload = (
        b"stacktrace: Exception in worker thread\nSegmentation fault (core dumped)"
    )
    att = store.save_attachment(
        issue_id=issue_id,
        filename="crash.log",
        content=payload,
        content_type="text/plain",
        uploaded_by="agent-crash-reporter",
    )
    assert att.filename == "crash.log"
    assert att.size_bytes == len(payload)
    assert len(att.sha256) == 64

    # Read back
    read_bytes = store.read_attachment_bytes(att.attachment_id)
    assert read_bytes == payload

    # List
    attachments = store.list_issue_attachments(issue_id)
    assert len(attachments) == 1


# ==============================================================================
# CheckoutManager Tests
# ==============================================================================


def test_checkout_lease():
    mgr = CheckoutManager()
    ticket_id = "ISSUE-LOCK1"

    assert mgr.is_claimed(ticket_id) is False

    chk = mgr.claim_ticket(ticket_id, claimed_by="agent-alpha", lease_seconds=10.0)
    assert chk.is_active is True
    assert mgr.is_claimed(ticket_id) is True

    # Same claimant can refresh/re-claim
    mgr.claim_ticket(ticket_id, claimed_by="agent-alpha", lease_seconds=20.0)

    # Different claimant blocked
    with pytest.raises(RuntimeError, match="already claimed"):
        mgr.claim_ticket(ticket_id, claimed_by="agent-beta")

    # Renew
    renewed = mgr.renew_lease(ticket_id, claimed_by="agent-alpha", extend_seconds=50.0)
    assert renewed.expires_at > time.time() + 30.0

    # Release
    assert mgr.release_ticket(ticket_id, claimed_by="agent-alpha") is True
    assert mgr.is_claimed(ticket_id) is False


# ==============================================================================
# TicketInbox Tests
# ==============================================================================


def test_ticket_inbox():
    issues = IssueManager()
    checkouts = CheckoutManager()
    inbox = TicketInbox(issue_manager=issues, checkout_manager=checkouts)

    i_crit = issues.create_issue(
        "Critical DB Outage", "DB down", severity=IssueSeverity.CRITICAL
    )
    i_minor = issues.create_issue(
        "Typo in Docs", "Docs typo", severity=IssueSeverity.MINOR
    )
    i_major = issues.create_issue(
        "High Latency", "API slow", severity=IssueSeverity.MAJOR
    )

    # Prioritized triage: CRITICAL should be first, then MAJOR, then MINOR
    queue = inbox.get_triage_queue()
    assert len(queue) == 3
    assert queue[0].issue_id == i_crit.issue_id
    assert queue[1].issue_id == i_major.issue_id
    assert queue[2].issue_id == i_minor.issue_id

    # Claim one issue and filter out claimed
    checkouts.claim_ticket(i_crit.issue_id, "worker-1")
    unclaimed = inbox.get_triage_queue(InboxFilter(include_claimed=False))
    assert len(unclaimed) == 2
    assert i_crit.issue_id not in [x.issue_id for x in unclaimed]

    # Assign one issue
    issues.assign(i_minor.issue_id, "worker-2")
    unassigned = inbox.get_unassigned_issues()
    assert len(unassigned) == 2

    # SLA Breaches
    i_crit.created_at = time.time() - 7200.0  # 2 hours old
    breaches = inbox.detect_sla_breaches(max_age_seconds=3600.0)
    assert len(breaches) == 1
    assert breaches[0].issue_id == i_crit.issue_id
