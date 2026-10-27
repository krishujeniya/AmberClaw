"""Common reusable API and domain schemas."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class StatusResponse(BaseModel):
    """Standard health or operational status response envelope."""

    status: str = Field(default="ok", description="Status code or string indicator.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    details: dict[str, Any] = Field(default_factory=dict)


class PaginationParams(BaseModel):
    """Query parameters for paginated endpoints."""

    page: int = Field(default=1, ge=1, description="1-indexed page number.")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page.")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard envelope for paginated collections."""

    items: list[T]
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    per_page: int = Field(..., ge=1)
    total_pages: int = Field(..., ge=0)


class RequestAuditMetadata(BaseModel):
    """Auditing and tracking context attached to API requests."""

    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    actor: str = Field(default="system")
    client_ip: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
