"""AmberClaw agent learning, feedback, and proactive nudging module."""

from pydantic import BaseModel, Field

from amberclaw.agent.learning.feedback import FeedbackCollector, UserFeedback
from amberclaw.agent.learning.memory_nudges import (
    MemoryNudgeEvaluator,
    MemoryNudgeSystem,
    NudgeEvent,
    NudgeTriggerType,
)
from amberclaw.agent.learning.skill_creator import SkillCreator
from amberclaw.agent.learning.skill_improver import SkillImprover


class LearningModuleConfig(BaseModel):
    """Configuration for the amberclaw.agent.learning module."""

    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = [
    "FeedbackCollector",
    "LearningModuleConfig",
    "MemoryNudgeEvaluator",
    "MemoryNudgeSystem",
    "NudgeEvent",
    "NudgeTriggerType",
    "SkillCreator",
    "SkillImprover",
    "UserFeedback",
]
