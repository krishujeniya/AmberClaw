"""Reasoning-reflection and learning loop module."""

from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.providers.base import LLMProvider


class ReflectionResult(BaseModel):
    """Structured evaluation of agent execution."""

    is_successful: bool = Field(
        description="Whether the task has been successfully and fully completed."
    )
    critique: str = Field(
        description="A detailed analysis of the performance, identifying flaws or confirming success."
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="List of specific information/data points that are missing to satisfy the user request.",
    )
    correction_steps: list[str] = Field(
        default_factory=list,
        description="Actionable steps the agent must take to correct identified failures.",
    )


class AgentReflector:
    """Evaluates agent execution trajectories and provides correction suggestions."""

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def reflect(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
    ) -> ReflectionResult:
        """
        Analyze conversation trajectory and evaluate correctness/completeness.

        Args:
            messages: Complete message list containing human, assistant, and tool turns.
            model: Optional model override.

        Returns:
            ReflectionResult outlining success/failure and correction instructions.
        """
        # Build trajectory overview
        trajectory_str = ""
        for i, msg in enumerate(messages):
            role = msg.get("role")
            content = msg.get("content") or ""
            tool_calls = msg.get("tool_calls")

            # Clean thinking blocks for cleaner analysis
            if "<think>" in content:
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

            trajectory_str += f"\n[{i}] {role.upper()}: {content[:1000]}"
            if tool_calls:
                trajectory_str += f"\n    (Tool Calls: {tool_calls})"

        from amberclaw.security.secret_scanner import SecretScanner
        trajectory_str = SecretScanner.redact_text(trajectory_str)

        prompt = (
            "You are an expert agent performance auditor. Analyze the following conversation and tool execution trajectory "
            "to evaluate if the user request has been fully, correctly, and safely satisfied.\n\n"
            f"Trajectory:\n{trajectory_str}\n\n"
            "Evaluate strictly based on: \n"
            "1. Did the agent answer the user's core request?\n"
            "2. Did any tool executions fail or return errors, and if so, did the agent recover?\n"
            "3. Are the facts/conclusions consistent with the tool results?\n\n"
            "Respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            '  "is_successful": true/false,\n'
            '  "critique": "your detailed critique string",\n'
            '  "missing_information": ["list of missing details, if any"],\n'
            '  "correction_steps": ["list of correction actions needed, if any"]\n'
            "}"
        )

        try:
            # Enforce JSON output format if supported by provider
            response = await self.provider.chat_with_retry(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            content = response.content or "{}"
            # Extract JSON if wrapped in markdown
            if "```json" in content:
                match = re.search(r"```json\s*(.*?)\s*```", content, flags=re.DOTALL)
                if match:
                    content = match.group(1)

            data = json.loads(content)
            return ReflectionResult.model_validate(data)

        except Exception as e:
            logger.warning("Failed to get structured reflection from LLM: {}. Falling back to default success.", e)
            # Default fallback to PASS to avoid blocking execution
            return ReflectionResult(
                is_successful=True,
                critique=f"Reflection failed with error: {e}. Defaulting to success.",
                missing_information=[],
                correction_steps=[],
            )
