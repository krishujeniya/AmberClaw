"""Memory Nudge System for proactive agent self-prompting."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, ClassVar

from loguru import logger


class MemoryNudgeSystem:
    """Proactively nudges the agent to capture key user facts and preferences."""

    PATTERN_KEYWORDS: ClassVar[list[str]] = [
        r"\bi\s+prefer\b",
        r"\balways\s+use\b",
        r"\bnever\s+do\b",
        r"\bremember\s+that\b",
        r"\bmy\s+workflow\b",
        r"\bdon't\s+forget\b",
        r"\bi\s+like\b",
        r"\bi\s+hate\b",
    ]

    # Turn-based nudge frequency
    TURN_FREQUENCY = 10

    def __init__(self, workspace: Path):
        self.workspace = workspace

    def should_nudge(self, messages: list[dict[str, Any]], last_message: str) -> str | None:
        """
        Evaluate if a nudge should be triggered.

        Args:
            messages: Full conversation history.
            last_message: The latest user message.

        Returns:
            The nudge system message text, or None if no nudge is needed.
        """
        # 1. Turn-based nudge (every 10 assistant turns)
        assistant_turns = sum(1 for m in messages if m.get("role") == "assistant")
        if assistant_turns > 0 and assistant_turns % self.TURN_FREQUENCY == 0:
            logger.info("MemoryNudgeSystem: Periodic turn-based nudge triggered (turn {})", assistant_turns)
            return (
                "[System Nudge] We have reached 10 turns in this session. "
                "Please review the conversation. If the user has stated any new preferences, "
                "workflows, or persistent facts, make sure to update long-term memory."
            )

        # 2. Pattern-based nudge (keywords in last user message)
        for pattern in self.PATTERN_KEYWORDS:
            if re.search(pattern, last_message, re.IGNORECASE):
                logger.info("MemoryNudgeSystem: Pattern-based nudge triggered by pattern '{}'", pattern)
                return (
                    "[System Nudge] The user just shared a potential preference or workflow rule. "
                    "Verify if you should record this preference or rule in long-term memory."
                )

        return None
