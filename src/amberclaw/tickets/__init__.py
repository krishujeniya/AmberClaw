"""AmberClaw enterprise ticketing, issue tracking, and operational work-stream management."""

from pydantic import BaseModel, Field

from amberclaw.tickets.attachments import Attachment, AttachmentStore
from amberclaw.tickets.checkout import CheckoutManager, TicketCheckout
from amberclaw.tickets.comments import Comment, CommentManager
from amberclaw.tickets.inbox import InboxFilter, TicketInbox
from amberclaw.tickets.issue import Issue, IssueManager, IssueSeverity, IssueStatus


class TicketsModuleConfig(BaseModel):
    """Configuration for the amberclaw.tickets module."""

    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")
    default_lease_seconds: float = Field(default=300.0, ge=10.0)


__all__ = [
    "Attachment",
    "AttachmentStore",
    "CheckoutManager",
    "Comment",
    "CommentManager",
    "InboxFilter",
    "Issue",
    "IssueManager",
    "IssueSeverity",
    "IssueStatus",
    "TicketCheckout",
    "TicketInbox",
    "TicketsModuleConfig",
]
