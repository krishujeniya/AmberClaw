"""Domain models representing autonomous Goal management."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class GoalStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ACHIEVED = "achieved"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class GoalModel(BaseModel):
    """An autonomous long-horizon goal pursued by an agent or team."""

    id: str = Field(..., description="Unique goal identifier.")
    title: str = Field(..., description="Goal summary title.")
    description: str = Field(default="", description="Detailed goal specification.")
    status: GoalStatus = Field(default=GoalStatus.PENDING, description="Current progress status.")
    priority: int = Field(default=1, ge=1, le=5, description="Priority level (1 highest, 5 lowest).")
    target_agent_id: str | None = Field(default=None, description="Assigned primary agent ID.")
    progress_percent: float = Field(default=0.0, ge=0.0, le=100.0, description="Completion percentage.")
    milestones: list[str] = Field(default_factory=list, description="Sub-milestone checkpoints.")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
