"""Domain model representing a Workspace execution environment."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkspaceModel(BaseModel):
    """Workspace boundary containing files, memory, and permissions."""

    id: str = Field(..., description="Unique workspace identifier.")
    name: str = Field(..., description="Human-readable workspace label.")
    root_path: str = Field(..., description="Root filesystem directory path.")
    company_id: str | None = Field(default=None, description="Owning organization ID.")
    is_isolated: bool = Field(default=True, description="Enforce sandboxed execution boundaries.")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    settings: dict[str, Any] = Field(default_factory=dict)
