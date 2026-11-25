"""Attachment metadata and storage manager for tickets and issues."""

import hashlib
import time
import uuid
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


class Attachment(BaseModel):
    """File attachment associated with an issue."""

    attachment_id: str = Field(
        default_factory=lambda: f"ATT-{uuid.uuid4().hex[:8].upper()}"
    )
    issue_id: str = Field(..., description="Target issue ID")
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(default="application/octet-stream")
    size_bytes: int = Field(default=0, ge=0)
    sha256: str = Field(..., description="Cryptographic SHA-256 hash of file content")
    storage_path: str = Field(..., description="Relative or absolute path on disk")
    uploaded_by: str = Field(default="system")
    uploaded_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AttachmentStore:
    """Manages file attachment storage and retrieval on the local filesystem."""

    def __init__(self, storage_dir: Path | str | None = None) -> None:
        self.storage_dir = Path(storage_dir or "data/attachments").resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._attachments: dict[str, Attachment] = {}

    def save_attachment(
        self,
        issue_id: str,
        filename: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        uploaded_by: str = "system",
    ) -> Attachment:
        """Save raw bytes as an attachment with hash verification."""
        sha256_hash = hashlib.sha256(content).hexdigest()
        att_id = f"ATT-{uuid.uuid4().hex[:8].upper()}"

        issue_folder = self.storage_dir / issue_id
        issue_folder.mkdir(parents=True, exist_ok=True)

        target_file = issue_folder / f"{att_id}_{filename}"
        target_file.write_bytes(content)

        attachment = Attachment(
            attachment_id=att_id,
            issue_id=issue_id,
            filename=filename,
            content_type=content_type,
            size_bytes=len(content),
            sha256=sha256_hash,
            storage_path=str(target_file),
            uploaded_by=uploaded_by,
        )
        self._attachments[att_id] = attachment
        logger.info(
            "Saved attachment [{}] for issue [{}] (size: {} bytes, sha256: {}...)",
            att_id,
            issue_id,
            len(content),
            sha256_hash[:8],
        )
        return attachment

    def get_attachment(self, attachment_id: str) -> Attachment | None:
        """Fetch attachment metadata by ID."""
        return self._attachments.get(attachment_id)

    def read_attachment_bytes(self, attachment_id: str) -> bytes:
        """Read and verify the content of an attachment."""
        att = self.get_attachment(attachment_id)
        if not att:
            raise KeyError(f"Attachment '{attachment_id}' not found.")

        target_file = Path(att.storage_path)
        if not target_file.exists():
            raise FileNotFoundError(f"Attachment file '{att.storage_path}' is missing.")

        content = target_file.read_bytes()
        computed_hash = hashlib.sha256(content).hexdigest()
        if computed_hash != att.sha256:
            raise ValueError(
                f"Attachment checksum mismatch! Expected {att.sha256}, got {computed_hash}"
            )

        return content

    def list_issue_attachments(self, issue_id: str) -> list[Attachment]:
        """List all attachments belonging to a particular issue."""
        return [a for a in self._attachments.values() if a.issue_id == issue_id]
