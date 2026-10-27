"""AmberClaw agent planning, reflection, and delegation module."""

from pydantic import BaseModel, Field

from amberclaw.agent.planning.delegation import DelegationPlanner, SubTaskAssignment
from amberclaw.agent.planning.react import ReActPlanner, ReActStep
from amberclaw.agent.planning.reflection import ReflectionCritique, ReflectionEngine


class PlanningModuleConfig(BaseModel):
    """Configuration for the amberclaw.agent.planning module."""

    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = [
    "DelegationPlanner",
    "PlanningModuleConfig",
    "ReActPlanner",
    "ReActStep",
    "ReflectionCritique",
    "ReflectionEngine",
    "SubTaskAssignment",
]
