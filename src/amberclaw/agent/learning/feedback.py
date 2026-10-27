"""User feedback collection, rating aggregation, and automated learning adjustment."""

from typing import Literal

from pydantic import BaseModel, Field


class UserFeedback(BaseModel):
    """User rating and qualitative feedback for an agent response."""

    session_id: str = Field(..., description="Target session identifier.")
    turn_index: int = Field(..., description="Message turn index.")
    rating: Literal["positive", "negative", "neutral"] = Field(
        ..., description="User sentiment rating."
    )
    critique: str | None = Field(default=None, description="Optional textual critique.")
    correction: str | None = Field(default=None, description="User-provided explicit correction.")
    tags: list[str] = Field(default_factory=list, description="Categorical tags (e.g. 'code', 'hallucination').")


class FeedbackCollector:
    """Stores and analyzes user feedback across sessions."""

    def __init__(self) -> None:
        self.feedback_store: list[UserFeedback] = []

    def record_feedback(self, feedback: UserFeedback) -> None:
        """Record user feedback entry."""
        self.feedback_store.append(feedback)

    def get_summary_stats(self) -> dict[str, int | float]:
        """Compute aggregated positive, negative, and satisfaction ratios."""
        total = len(self.feedback_store)
        if total == 0:
            return {"total": 0, "positive": 0, "negative": 0, "neutral": 0, "satisfaction_rate": 1.0}

        positive = sum(1 for f in self.feedback_store if f.rating == "positive")
        negative = sum(1 for f in self.feedback_store if f.rating == "negative")
        neutral = sum(1 for f in self.feedback_store if f.rating == "neutral")

        satisfaction_rate = round(positive / total, 2)
        return {
            "total": total,
            "positive": positive,
            "negative": negative,
            "neutral": neutral,
            "satisfaction_rate": satisfaction_rate,
        }

    def get_corrections(self) -> list[dict[str, str]]:
        """Extract explicit user corrections for memory/prompt refinement."""
        return [
            {
                "session_id": f.session_id,
                "critique": f.critique or "",
                "correction": f.correction,
            }
            for f in self.feedback_store
            if f.correction is not None
        ]
