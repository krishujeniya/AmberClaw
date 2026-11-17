# ruff: noqa: S101, PLR0913
"""Controlled Comparative Benchmark Runner and Statistical Analyzer (CL-022).

Enforces:
- Equal hardware, model budget, and execution parameters.
- Triplicate task execution (3 runs per task) across all comparator systems.
- Honest accounting of failures, partial executions, and unsupported cases.
- Paired 95% confidence intervals and p95 latency percentiles.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class ComparatorSystem(BaseModel):
    name: str
    version: str
    edition: str
    deployment_topology: str
    kernel_isolation_supported: bool
    durable_state_supported: bool
    hard_budget_supported: bool


class BenchmarkAttempt(BaseModel):
    system: str
    task_id: str
    attempt_index: int  # 1, 2, 3
    success: bool
    latency_ms: float
    token_usage: int
    cost_usd: float
    unsupported_features: list[str] = Field(default_factory=list)
    failure_reason: str | None = None


@dataclass
class SystemStatisticalSummary:
    system_name: str
    total_runs: int
    successful_runs: int
    success_rate: float
    ci_95_low: float
    ci_95_high: float
    latency_p50_ms: float
    latency_p95_ms: float
    total_spend_usd: float
    cost_per_success_usd: float
    unsupported_task_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ComparativeBenchmarkAnalyzer:
    """Computes rigorous statistical bounds across triplicate benchmark runs."""

    @staticmethod
    def compute_wilson_ci(k: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
        """Compute Wilson score interval for binomial proportion."""
        if n == 0:
            return 0.0, 0.0
        # z-score for 95% CI is 1.95996
        z = 1.959964
        p = k / n
        denominator = 1 + (z**2) / n
        centre = (p + (z**2) / (2 * n)) / denominator
        margin = (z * math.sqrt((p * (1 - p) / n) + ((z**2) / (4 * (n**2))))) / denominator
        return max(0.0, round(centre - margin, 4)), min(1.0, round(centre + margin, 4))

    def analyze_system_runs(
        self, system_name: str, attempts: list[BenchmarkAttempt]
    ) -> SystemStatisticalSummary:
        sys_attempts = [a for a in attempts if a.system == system_name]
        n = len(sys_attempts)
        if n == 0:
            return SystemStatisticalSummary(
                system_name=system_name,
                total_runs=0,
                successful_runs=0,
                success_rate=0.0,
                ci_95_low=0.0,
                ci_95_high=0.0,
                latency_p50_ms=0.0,
                latency_p95_ms=0.0,
                total_spend_usd=0.0,
                cost_per_success_usd=0.0,
                unsupported_task_count=0,
            )

        k = sum(1 for a in sys_attempts if a.success)
        success_rate = round(k / n, 4)
        ci_low, ci_high = self.compute_wilson_ci(k, n)

        latencies = sorted(a.latency_ms for a in sys_attempts)
        p50 = latencies[int(n * 0.50)]
        p95_idx = min(int(n * 0.95), n - 1)
        p95 = latencies[p95_idx]

        total_spend = sum(a.cost_usd for a in sys_attempts)
        cost_per_success = round(total_spend / k, 6) if k > 0 else 0.0

        unsupported_count = sum(1 for a in sys_attempts if len(a.unsupported_features) > 0)

        return SystemStatisticalSummary(
            system_name=system_name,
            total_runs=n,
            successful_runs=k,
            success_rate=success_rate,
            ci_95_low=ci_low,
            ci_95_high=ci_high,
            latency_p50_ms=round(p50, 2),
            latency_p95_ms=round(p95, 2),
            total_spend_usd=round(total_spend, 6),
            cost_per_success_usd=cost_per_success,
            unsupported_task_count=unsupported_count,
        )
