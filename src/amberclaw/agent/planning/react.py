"""ReAct (Reasoning and Acting) execution planning step parser and tracker."""

import json
import re
from typing import Any

from pydantic import BaseModel, Field


class ReActStep(BaseModel):
    """A single step in a ReAct loop trajectory."""

    thought: str = Field(default="", description="Chain-of-thought rationale.")
    action: str | None = Field(default=None, description="Selected tool name to call.")
    action_input: dict[str, Any] | str | None = Field(default=None, description="Tool input arguments.")
    observation: str | None = Field(default=None, description="Result observed after tool execution.")
    is_final: bool = Field(default=False, description="Whether this step concluded the plan.")
    final_response: str | None = Field(default=None, description="Final answer delivered to the user.")


class ReActPlanner:
    """Parses and manages ReAct reasoning and acting trajectories."""

    def __init__(self, max_steps: int = 10) -> None:
        self.max_steps = max_steps
        self.steps: list[ReActStep] = []

    def parse_step(self, text: str) -> ReActStep:
        """Parse raw LLM response into structured ReActStep."""
        thought_match = re.search(r"Thought:\s*(.*?)(?=(?:Action:|Final Answer:|$))", text, re.DOTALL | re.IGNORECASE)
        action_match = re.search(r"Action:\s*([a-zA-Z0-9_\-\.]+)", text, re.IGNORECASE)
        action_input_match = re.search(r"Action Input:\s*(.*?)(?=(?:Observation:|Thought:|$))", text, re.DOTALL | re.IGNORECASE)
        final_answer_match = re.search(r"Final Answer:\s*(.*)", text, re.DOTALL | re.IGNORECASE)

        thought = thought_match.group(1).strip() if thought_match else text.strip()

        if final_answer_match:
            final_resp = final_answer_match.group(1).strip()
            step = ReActStep(thought=thought, is_final=True, final_response=final_resp)
            self.steps.append(step)
            return step

        action = action_match.group(1).strip() if action_match else None
        action_input_raw = action_input_match.group(1).strip() if action_input_match else None
        action_input: Any = action_input_raw

        if action_input_raw and (action_input_raw.startswith("{") or action_input_raw.startswith("[")):
            try:
                action_input = json.loads(action_input_raw)
            except Exception:
                action_input = action_input_raw

        step = ReActStep(thought=thought, action=action, action_input=action_input, is_final=False)
        self.steps.append(step)
        return step

    def record_observation(self, observation: str) -> None:
        """Attach an observation to the most recent step."""
        if self.steps and not self.steps[-1].is_final:
            self.steps[-1].observation = observation

    def is_finished(self) -> bool:
        """Check if plan completed or reached max step limit."""
        if not self.steps:
            return False
        if self.steps[-1].is_final:
            return True
        return len(self.steps) >= self.max_steps
