"""Domain model representing an Enterprise / Organization entity."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CompanyModel(BaseModel):
    """Organization / Tenant entity boundary."""

    id: str = Field(..., description="Unique organization identifier.")
    name: str = Field(..., description="Company name.")
    domain: str | None = Field(default=None, description="Primary domain identifier.")
    departments: list[str] = Field(default_factory=list, description="Registered organizational departments.")
    settings: dict[str, Any] = Field(default_factory=dict, description="Tenant-level configurations.")
    created_at: datetime = Field(default_factory=datetime.utcnow)
