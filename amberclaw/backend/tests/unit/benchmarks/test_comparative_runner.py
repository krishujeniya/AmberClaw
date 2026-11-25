# ruff: noqa: PLR2004
"""Unit tests for CL-022: Controlled Comparative Benchmark Runner and Stats."""

from __future__ import annotations

import pytest

from amberclaw.benchmarks.comparative_runner import (
    BenchmarkAttempt,
    ComparativeBenchmarkAnalyzer,
)


def test_wilson_ci_computation():
    """Verify statistical correctness of Wilson score interval bounds."""
    analyzer = ComparativeBenchmarkAnalyzer()

    # 15/15 successes (100% success)
    low, high = analyzer.compute_wilson_ci(15, 15)
    assert low > 0.75
    assert high == 1.0

    # 0/15 successes (0% success)
    low_0, high_0 = analyzer.compute_wilson_ci(0, 15)
    assert low_0 == 0.0
    assert high_0 < 0.25

    # 12/15 successes (80% success)
    low_mid, high_mid = analyzer.compute_wilson_ci(12, 15)
    assert 0.50 < low_mid < 0.80
    assert 0.80 < high_mid < 0.98


def test_system_statistical_summary_triplicate_runs():
    """Verify statistical summary across triplicate task attempts."""
    analyzer = ComparativeBenchmarkAnalyzer()

    attempts = [
        # AmberClaw (5 tasks * 3 runs = 15 runs, 15 successes)
        BenchmarkAttempt(
            system="AmberClaw",
            task_id=f"task_{i}",
            attempt_index=j,
            success=True,
            latency_ms=45.0 + (i * 2) + j,
            token_usage=120,
            cost_usd=0.0006,
        )
        for i in range(5)
        for j in range(1, 4)
    ]

    # Add a comparator with failures and unsupported features
    for i in range(5):
        for j in range(1, 4):
            # Task 4 unsupported (e.g. kernel isolation)
            is_unsupp = (i == 4)
            success = not is_unsupp and (j < 3 or i != 2)
            attempts.append(
                BenchmarkAttempt(
                    system="ComparatorA",
                    task_id=f"task_{i}",
                    attempt_index=j,
                    success=success,
                    latency_ms=120.0 + (i * 10) + j,
                    token_usage=250,
                    cost_usd=0.0015,
                    unsupported_features=["kernel_landlock_sandbox"] if is_unsupp else [],
                )
            )

    summary_amberclaw = analyzer.analyze_system_runs("AmberClaw", attempts)
    assert summary_amberclaw.total_runs == 15
    assert summary_amberclaw.successful_runs == 15
    assert summary_amberclaw.success_rate == 1.0
    assert summary_amberclaw.unsupported_task_count == 0
    assert summary_amberclaw.cost_per_success_usd > 0.0
    assert summary_amberclaw.latency_p95_ms > summary_amberclaw.latency_p50_ms

    summary_comp = analyzer.analyze_system_runs("ComparatorA", attempts)
    assert summary_comp.total_runs == 15
    assert summary_comp.successful_runs < 15
    assert summary_comp.unsupported_task_count == 3
    assert summary_comp.latency_p95_ms > summary_amberclaw.latency_p95_ms
