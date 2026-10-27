"""Commentary and discussion threads on operational tickets."""

import time
import uuid

from loguru import logger
from pydantic import BaseModel, Field


class Comment(BaseModel):
    """Discussion entry attached to an issue or ticket."""

    comment_id: str = Field(
        default_factory=lambda: f"CMT-{uuid.uuid4().hex[:8].upper()}"
    )
    issue_id: str = Field(..., description="Target issue ID")
    author: str = Field(..., description="Operator or agent ID")
    content: str = Field(..., description="Message text or explanation")
    is_internal: bool = Field(
        default=False,
        description="Whether comment is hidden from external stakeholders",
    )
    created_at: float = Field(default_factory=time.time)
    edited_at: float | None = None


class CommentManager:
    """Manages comment threads associated with operational issues."""

    def __init__(self) -> None:
        self._comments: dict[str, list[Comment]] = {}  # issue_id -> comments

    def add_comment(
        self,
        issue_id: str,
        author: str,
        content: str,
        is_internal: bool = False,
    ) -> Comment:
        """Add a comment to an issue thread."""
        comment = Comment(
            issue_id=issue_id,
            author=author,
            content=content,
            is_internal=is_internal,
        )
        self._comments.setdefault(issue_id, []).append(comment)
        logger.info(
            "Added comment [{}] to issue [{}] by '{}'",
            comment.comment_id,
            issue_id,
            author,
        )
        return comment

    def get_comments(
        self,
        issue_id: str,
        include_internal: bool = True,
    ) -> list[Comment]:
        """Retrieve chronological comments for an issue."""
        comments = self._comments.get(issue_id, [])
        if not include_internal:
            return [c for c in comments if not c.is_internal]
        return list(comments)

    def delete_comment(self, issue_id: str, comment_id: str) -> bool:
        """Remove a comment by comment ID."""
        if issue_id not in self._comments:
            return False
        original_len = len(self._comments[issue_id])
        self._comments[issue_id] = [
            c for c in self._comments[issue_id] if c.comment_id != comment_id
        ]
        return len(self._comments[issue_id]) < original_len
