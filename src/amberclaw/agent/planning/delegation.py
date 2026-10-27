"""Sub-task decomposition and agent delegation planning engine."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class SubTaskAssignment(BaseModel):
    """A delegated sub-task unit within an execution plan."""

    subtask_id: str = Field(..., description="Unique identifier for the subtask.")
    title: str = Field(..., description="Short summary of the subtask.")
    target_role: str = Field(..., description="Assigned role or agent capability.")
    dependencies: list[str] = Field(default_factory=list, description="IDs of subtasks that must complete first.")
    payload: dict[str, Any] = Field(default_factory=dict, description="Parameters or payload for the subtask.")
    status: Literal["pending", "in_progress", "completed", "failed"] = Field(
        default="pending", description="Current status of the subtask."
    )


class DelegationPlanner:
    """Decomposes complex objectives into structured sub-task DAGs."""

    def __init__(self) -> None:
        self.subtasks: dict[str, SubTaskAssignment] = {}

    def add_subtask(self, subtask: SubTaskAssignment) -> None:
        """Add a subtask to the planner."""
        self.subtasks[subtask.subtask_id] = subtask

    def get_executable_subtasks(self) -> list[SubTaskAssignment]:
        """Return all pending subtasks whose dependencies are all completed."""
        ready: list[SubTaskAssignment] = []
        for task in self.subtasks.values():
            if task.status != "pending":
                continue
            deps_met = all(
                dep_id in self.subtasks and self.subtasks[dep_id].status == "completed"
                for dep_id in task.dependencies
            )
            if deps_met:
                ready.append(task)
        return ready

    def mark_completed(self, subtask_id: str) -> None:
        """Mark a subtask as completed."""
        if subtask_id in self.subtasks:
            self.subtasks[subtask_id].status = "completed"

    def mark_failed(self, subtask_id: str) -> None:
        """Mark a subtask as failed."""
        if subtask_id in self.subtasks:
            self.subtasks[subtask_id].status = "failed"

    def is_all_completed(self) -> bool:
        """Check if all planned subtasks have completed successfully."""
        return bool(self.subtasks) and all(t.status == "completed" for t in self.subtasks.values())

    def has_failures(self) -> bool:
        """Check if any subtask has failed."""
        return any(t.status == "failed" for t in self.subtasks.values())
