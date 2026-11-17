# ruff: noqa: PLR2004
"""Unit tests for CL-015: Hard Budgets, In-Flight Settlement, and Cost per Success."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from amberclaw.runtime.budget_ledger import (
    BudgetExceededError,
    BudgetTimeoutError,
    HardBudgetLedger,
)


@pytest.fixture(autouse=True)
def clean_ledger():
    ledger = HardBudgetLedger.get_instance()
    ledger.reset()
    yield
    ledger.reset()


@pytest.mark.asyncio
async def test_concurrent_budget_reservations_cannot_exceed_cap():
    """Verify concurrent parallel calls cannot bypass declared spend cap."""
    ledger = HardBudgetLedger.get_instance()
    # $1.00 budget with 5% allowance ($1.05 max total capacity)
    ledger.configure_tenant(
        tenant_id="tenant_cap_test",
        max_budget_usd=1.00,
        settlement_allowance_ratio=0.05,
    )

    success_count = 0
    denied_count = 0

    async def attempt_call(idx: int) -> bool:
        nonlocal success_count, denied_count
        try:
            # Each call requests $0.20 reservation
            res = await ledger.reserve(
                tenant_id="tenant_cap_test",
                run_id=f"run_conc_{idx}",
                estimated_usd=0.20,
            )
            # Settle actual cost
            await ledger.settle(
                reservation_id=res.reservation_id,
                actual_usd=0.20,
                action_type="model_inference",
                status="success",
            )
            success_count += 1
            return True
        except BudgetExceededError:
            denied_count += 1
            return False

    # Launch 10 concurrent requests ($2.00 total attempted)
    tasks = [attempt_call(i) for i in range(10)]
    results = await asyncio.gather(*tasks)

    # Exactly 5 should succeed ($1.00 total), 5 should be blocked
    assert success_count == 5
    assert denied_count == 5
    assert sum(results) == 5

    spend = await ledger.get_tenant_spend("tenant_cap_test")
    assert spend["total_spent_usd"] == 1.00
    assert spend["in_flight_reserved_usd"] == 0.0
    assert spend["remaining_budget_usd"] == 0.0


@pytest.mark.asyncio
async def test_failed_attempts_and_retries_accounted_in_ledger():
    """Verify failed attempts and retries are recorded and included in total spend."""
    ledger = HardBudgetLedger.get_instance()
    ledger.configure_tenant("tenant_retry_test", max_budget_usd=5.0)

    # 1. First attempt fails after consuming tokens
    res1 = await ledger.reserve(
        tenant_id="tenant_retry_test",
        run_id="run_retry_01",
        estimated_usd=0.50,
        step_index=0,
    )
    await ledger.settle(
        reservation_id=res1.reservation_id,
        actual_usd=0.45,
        actual_tokens=1500,
        action_type="model_inference",
        status="failed",
        latency_ms=320.0,
        error="Model context length exceeded",
    )

    # 2. Retry attempt succeeds
    res2 = await ledger.reserve(
        tenant_id="tenant_retry_test",
        run_id="run_retry_01",
        estimated_usd=0.40,
        step_index=0,
    )
    await ledger.settle(
        reservation_id=res2.reservation_id,
        actual_usd=0.35,
        actual_tokens=1100,
        action_type="model_inference",
        status="success",
        latency_ms=180.0,
    )
    await ledger.record_run_outcome("run_retry_01", "completed")

    spend = await ledger.get_tenant_spend("tenant_retry_test")
    # Both the 0.45 failed attempt and 0.35 success must be billed
    assert spend["total_spent_usd"] == 0.80
    assert spend["total_tokens_used"] == 2600

    metrics = await ledger.get_cost_per_success_metrics("tenant_retry_test")
    assert metrics["successful_runs"] == 1
    assert metrics["failed_runs"] == 0
    # Cost per success must include the cost of the failed attempt
    assert metrics["cost_per_successful_task_usd"] == 0.80


@pytest.mark.asyncio
async def test_run_timeout_ceiling_enforcement():
    """Verify run duration ceiling terminates subsequent step reservations."""
    ledger = HardBudgetLedger.get_instance()
    ledger.configure_tenant(
        tenant_id="tenant_timeout_test",
        max_budget_usd=10.0,
        max_run_duration_seconds=0.05,  # 50ms ceiling
    )

    # Initial step within ceiling
    res1 = await ledger.reserve(
        tenant_id="tenant_timeout_test",
        run_id="run_slow_01",
        estimated_usd=0.10,
    )
    await ledger.settle(res1.reservation_id, actual_usd=0.10)

    # Sleep past duration ceiling
    await asyncio.sleep(0.06)

    # Subsequent step must be rejected with timeout ceiling
    with pytest.raises(BudgetTimeoutError, match="exceeded maximum allotted duration"):
        await ledger.reserve(
            tenant_id="tenant_timeout_test",
            run_id="run_slow_01",
            estimated_usd=0.10,
        )


@pytest.mark.asyncio
async def test_cost_per_success_and_latency_profiles():
    """Verify quantitative yield, cost per success, and p50/p95 latency metrics."""
    ledger = HardBudgetLedger.get_instance()
    ledger.configure_tenant("tenant_analytics", max_budget_usd=100.0)

    # 3 successful runs ($0.20 each, latencies: 100ms, 150ms, 200ms)
    for i, lat in enumerate([100.0, 150.0, 200.0]):
        run_id = f"succ_run_{i}"
        res = await ledger.reserve("tenant_analytics", run_id, 0.20)
        await ledger.settle(res.reservation_id, actual_usd=0.20, actual_tokens=500, latency_ms=lat)
        await ledger.record_run_outcome(run_id, "completed")

    # 1 failed run ($0.40 total, latency: 400ms)
    run_fail = "fail_run_01"
    res_f = await ledger.reserve("tenant_analytics", run_fail, 0.40)
    await ledger.settle(res_f.reservation_id, actual_usd=0.40, actual_tokens=1000, status="failed", latency_ms=400.0)
    await ledger.record_run_outcome(run_fail, "failed")

    metrics = await ledger.get_cost_per_success_metrics("tenant_analytics")

    # Total spend = 3 * 0.20 + 0.40 = 1.00
    assert metrics["total_spend_usd"] == 1.00
    assert metrics["total_tokens"] == 2500
    assert metrics["successful_runs"] == 3
    assert metrics["failed_runs"] == 1
    assert metrics["task_success_rate"] == 0.75

    # Cost per successful task = $1.00 / 3 = 0.333333
    assert metrics["cost_per_successful_task_usd"] == round(1.0 / 3.0, 6)

    # Latencies: [100.0, 150.0, 200.0, 400.0] -> p50 = 200.0, p95 = 400.0
    assert metrics["latency_p50_ms"] == 200.0
    assert metrics["latency_p95_ms"] == 400.0


if __name__ == "__main__":
    async def run_all():
        print("Running test_concurrent_budget_reservations_cannot_exceed_cap...")
        await test_concurrent_budget_reservations_cannot_exceed_cap()
        HardBudgetLedger.get_instance().reset()

        print("Running test_failed_attempts_and_retries_accounted_in_ledger...")
        await test_failed_attempts_and_retries_accounted_in_ledger()
        HardBudgetLedger.get_instance().reset()

        print("Running test_run_timeout_ceiling_enforcement...")
        await test_run_timeout_ceiling_enforcement()
        HardBudgetLedger.get_instance().reset()

        print("Running test_cost_per_success_and_latency_profiles...")
        await test_cost_per_success_and_latency_profiles()
        HardBudgetLedger.get_instance().reset()

        print("ALL 4 BUDGET & COST TESTS PASSED SUCCESSFULLY!")

    asyncio.run(run_all())
