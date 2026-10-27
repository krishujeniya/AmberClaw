"""Telemetry and usage metrics tracker for skills."""

import time

from pydantic import BaseModel, Field, computed_field


class SkillUsageMetric(BaseModel):
    """Aggregate invocation statistics for a single skill."""

    skill_name: str
    invocations: int = Field(default=0)
    successes: int = Field(default=0)
    failures: int = Field(default=0)
    total_execution_time_ms: float = Field(default=0.0)
    last_invoked_at: float | None = Field(default=None)

    @computed_field
    @property
    def success_rate(self) -> float:
        if self.invocations == 0:
            return 1.0
        return round(self.successes / self.invocations, 2)

    @computed_field
    @property
    def avg_execution_time_ms(self) -> float:
        if self.invocations == 0:
            return 0.0
        return round(self.total_execution_time_ms / self.invocations, 2)


class SkillUsageTracker:
    """Tracks runtime execution counts, durations, and health across skills."""

    def __init__(self) -> None:
        self.metrics: dict[str, SkillUsageMetric] = {}

    def record_execution(
        self,
        skill_name: str,
        duration_ms: float,
        success: bool = True,
    ) -> SkillUsageMetric:
        """Record a single skill invocation result."""
        if skill_name not in self.metrics:
            self.metrics[skill_name] = SkillUsageMetric(skill_name=skill_name)

        m = self.metrics[skill_name]
        m.invocations += 1
        if success:
            m.successes += 1
        else:
            m.failures += 1
        m.total_execution_time_ms += duration_ms
        m.last_invoked_at = time.time()
        return m

    def get_metric(self, skill_name: str) -> SkillUsageMetric | None:
        """Retrieve metrics for a specific skill."""
        return self.metrics.get(skill_name)

    def get_all_metrics(self) -> list[SkillUsageMetric]:
        """List all tracked skill metrics."""
        return list(self.metrics.values())
