"""Memory nudge evaluators and trigger dispatchers."""

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from amberclaw.agent.learning.nudge_system import MemoryNudgeSystem


class NudgeTriggerType(StrEnum):
    PERIODIC_TURN = "periodic_turn"
    KEYWORD_PATTERN = "keyword_pattern"
    CONTRADICTION = "contradiction"


class NudgeEvent(BaseModel):
    """Event emitted when a memory nudge condition is satisfied."""

    trigger_type: NudgeTriggerType
    message: str
    context_turn: int = Field(default=0)


class MemoryNudgeEvaluator:
    """Evaluates agent interactions and emits structured nudge events."""

    def __init__(self, workspace: Path) -> None:
        self.underlying_system = MemoryNudgeSystem(workspace=workspace)

    def evaluate(
        self, messages: list[dict[str, Any]], last_message: str
    ) -> NudgeEvent | None:
        """Evaluate conversation history and trigger appropriate nudge event."""
        nudge_text = self.underlying_system.should_nudge(messages, last_message)
        if not nudge_text:
            return None

        assistant_turns = sum(1 for m in messages if m.get("role") == "assistant")
        if assistant_turns > 0 and assistant_turns % self.underlying_system.TURN_FREQUENCY == 0:
            trigger_type = NudgeTriggerType.PERIODIC_TURN
        else:
            trigger_type = NudgeTriggerType.KEYWORD_PATTERN

        return NudgeEvent(
            trigger_type=trigger_type,
            message=nudge_text,
            context_turn=assistant_turns,
        )


__all__ = [
    "MemoryNudgeEvaluator",
    "MemoryNudgeSystem",
    "NudgeEvent",
    "NudgeTriggerType",
]
