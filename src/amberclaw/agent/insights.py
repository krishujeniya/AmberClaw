"""Interaction insights and user preference mining engine."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentInsight(BaseModel):
    """An actionable pattern or preference derived from user interactions."""

    insight_type: Literal["preference", "workflow", "error_pattern", "skill_suggestion"]
    description: str
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    actionable_recommendation: str


class InsightsEngine:
    """Mines interaction histories to derive user habits and workflow recommendations."""

    def extract_insights(self, messages: list[dict[str, Any]]) -> list[AgentInsight]:
        """Analyze message history and generate actionable insights."""
        insights: list[AgentInsight] = []

        all_text = " ".join(str(m.get("content", "")) for m in messages).lower()

        # 1. Preferred programming language detection
        if "python" in all_text or ".py" in all_text or "pytest" in all_text:
            insights.append(
                AgentInsight(
                    insight_type="preference",
                    description="User frequently interacts with Python codebases and testing suites.",
                    confidence=0.9,
                    actionable_recommendation="Default to Python examples and pytest idioms when generating code.",
                )
            )
        if "docker" in all_text or "compose" in all_text or "k8s" in all_text:
            insights.append(
                AgentInsight(
                    insight_type="workflow",
                    description="User employs containerized deployment workflows (Docker/Kubernetes).",
                    confidence=0.85,
                    actionable_recommendation="Offer Docker Compose or Helm configurations proactively.",
                )
            )

        # 2. Frequent tool errors / issues
        if "permission denied" in all_text or "access denied" in all_text:
            insights.append(
                AgentInsight(
                    insight_type="error_pattern",
                    description="User encounters security sandbox or file permission constraints.",
                    confidence=0.88,
                    actionable_recommendation="Check RBAC policies and sandbox permissions before executing sensitive operations.",
                )
            )

        # 3. Code linting preferences
        if "ruff" in all_text or "formatting" in all_text:
            insights.append(
                AgentInsight(
                    insight_type="skill_suggestion",
                    description="User emphasizes automated linting and formatting compliance.",
                    confidence=0.92,
                    actionable_recommendation="Run ruff check automatically following file modifications.",
                )
            )

        return insights
