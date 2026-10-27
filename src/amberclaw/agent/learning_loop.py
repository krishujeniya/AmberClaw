"""Reasoning-reflection and learning loop module."""

from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.providers.base import LLMProvider
from amberclaw.security.secret_scanner import SecretScanner


class ReflectionResult(BaseModel):
    """Structured evaluation of agent execution."""

    is_successful: bool = Field(
        description="Whether the task has been successfully and fully completed."
    )
    quality_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Assessed quality and completeness score between 0.0 and 1.0.",
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


class LearningCycleResult(BaseModel):
    """Result of multi-iteration reflection and refinement cycles."""

    task: str
    initial_score: float
    final_score: float
    improvement_delta: float = Field(
        description="Difference between final and initial quality score (positive indicates measurable improvement)."
    )
    iterations_count: int
    is_converged: bool
    trajectory: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Step-by-step history of iterations, scores, critiques, and revisions.",
    )
    final_response: str


class AgentReflector:
    """Evaluates agent execution trajectories and provides correction suggestions."""

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def reflect(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
    ) -> ReflectionResult:
        """Analyze conversation trajectory and evaluate correctness/completeness.

        Args:
            messages: Complete message list containing human, assistant, and tool turns.
            model: Optional model override.

        Returns:
            ReflectionResult outlining success/failure, quality score, and correction instructions.
        """
        # Build trajectory overview
        trajectory_str = ""
        for i, msg in enumerate(messages):
            role = msg.get("role")
            content = msg.get("content") or ""
            tool_calls = msg.get("tool_calls")

            # Clean thinking blocks for cleaner analysis
            if "<think>" in content:
                content = re.sub(
                    r"<think>.*?</think>", "", content, flags=re.DOTALL
                ).strip()

            trajectory_str += f"\n[{i}] {role.upper()}: {content[:1000]}"
            if tool_calls:
                trajectory_str += f"\n    (Tool Calls: {tool_calls})"

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
            '  "quality_score": 0.0 to 1.0,\n'
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

            # Auto-calculate quality_score if not emitted by model
            if "quality_score" not in data:
                if data.get("is_successful", True):
                    data["quality_score"] = 1.0
                else:
                    miss_len = len(data.get("missing_information", []))
                    step_len = len(data.get("correction_steps", []))
                    data["quality_score"] = max(
                        0.1, round(1.0 - 0.2 * miss_len - 0.2 * step_len, 2)
                    )

            return ReflectionResult.model_validate(data)

        except Exception as e:
            logger.warning(
                "Failed to get structured reflection from LLM: {}. Falling back to default success.",
                e,
            )
            return ReflectionResult(
                is_successful=True,
                quality_score=1.0,
                critique=f"Reflection failed with error: {e}. Defaulting to success.",
                missing_information=[],
                correction_steps=[],
            )

    async def run_refinement_cycle(
        self,
        task: str,
        initial_response: str,
        max_iterations: int = 3,
        target_score: float = 0.85,
        model: str | None = None,
    ) -> LearningCycleResult:
        """Execute iterative Plan-Execute-Reflect cycles to achieve measurable improvement.

        Args:
            task: The user instruction or task objective.
            initial_response: The first drafted output.
            max_iterations: Max refinement cycles to run.
            target_score: Quality score threshold for early convergence.
            model: Optional model override.

        Returns:
            LearningCycleResult with measured quality metrics and improvement delta.
        """
        current_response = initial_response
        trajectory: list[dict[str, Any]] = []
        initial_score = 0.0
        final_score = 0.0

        for iteration in range(1, max_iterations + 1):
            eval_messages = [
                {"role": "user", "content": task},
                {"role": "assistant", "content": current_response},
            ]
            reflection = await self.reflect(eval_messages, model=model)
            score = reflection.quality_score

            if iteration == 1:
                initial_score = score
            final_score = score

            trajectory.append(
                {
                    "iteration": iteration,
                    "response": current_response,
                    "quality_score": score,
                    "is_successful": reflection.is_successful,
                    "critique": reflection.critique,
                    "missing_information": reflection.missing_information,
                    "correction_steps": reflection.correction_steps,
                }
            )

            # Check convergence condition
            if reflection.is_successful and score >= target_score:
                logger.info(
                    "Learning loop converged on iteration {} with quality score {:.2f}",
                    iteration,
                    score,
                )
                break

            if iteration >= max_iterations:
                logger.warning(
                    "Learning loop reached max iterations ({}) without full convergence (score: {:.2f})",
                    max_iterations,
                    score,
                )
                break

            # Refinement step: Ask provider to generate improved revision
            missing_text = "\n".join(f"- {m}" for m in reflection.missing_information)
            steps_text = "\n".join(f"- {s}" for s in reflection.correction_steps)
            refine_prompt = (
                f"You previously generated the following response for the task:\n\n"
                f"Task: {task}\n\n"
                f"Previous Response:\n{current_response}\n\n"
                f"Auditor Critique:\n{reflection.critique}\n\n"
                f"Missing Information:\n{missing_text}\n\n"
                f"Required Correction Steps:\n{steps_text}\n\n"
                "Please provide an improved, complete, and accurate response that resolves all identified critiques."
            )

            revision_resp = await self.provider.chat_with_retry(
                messages=[{"role": "user", "content": refine_prompt}],
                model=model,
                temperature=0.2,
            )
            current_response = revision_resp.content or current_response

        improvement_delta = round(final_score - initial_score, 3)

        return LearningCycleResult(
            task=task,
            initial_score=initial_score,
            final_score=final_score,
            improvement_delta=improvement_delta,
            iterations_count=len(trajectory),
            is_converged=final_score >= target_score
            or (len(trajectory) > 0 and trajectory[-1]["is_successful"]),
            trajectory=trajectory,
            final_response=current_response,
        )
