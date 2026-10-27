# ruff: noqa: PLR2004
"""Unit tests for telemetry sampling, cardinality bounding, bulkheads, and safe-mode boot."""

from __future__ import annotations

import pytest

from amberclaw.bootstrap import SafeModeBootstrapper
from amberclaw.observability.metrics import (
    CardinalityLimiter,
    TelemetrySampler,
    record_request_metric,
)
from amberclaw.providers.resilience import (
    Bulkhead,
    BulkheadExhaustedError,
    CircuitBreaker,
)


def test_cardinality_limiter_path_normalization():
    # UUID path normalization
    uuid_path = "/api/v1/tickets/12345678-1234-5678-1234-567812345678/approve"
    assert CardinalityLimiter.normalize_path(uuid_path) == "/api/v1/tickets/:id/approve"

    # Numeric ID path normalization
    int_path = "/api/v1/users/9876543/profile"
    assert CardinalityLimiter.normalize_path(int_path) == "/api/v1/users/:id/profile"

    # Fixed paths remain untouched
    fixed_path = "/api/v1/chat"
    assert CardinalityLimiter.normalize_path(fixed_path) == "/api/v1/chat"


def test_telemetry_sampler():
    sampler_always = TelemetrySampler(sample_rate=1.0)
    assert sampler_always.should_sample()
    assert sampler_always.should_sample(trace_id="trace_abc123")

    sampler_never = TelemetrySampler(sample_rate=0.0)
    assert not sampler_never.should_sample()
    assert not sampler_never.should_sample(trace_id="trace_abc123")

    # Record metric with safe path
    record_request_metric(
        method="GET",
        endpoint="/api/v1/sessions/12345678-1234-5678-1234-567812345678",
        status_code=200,
        duration_seconds=0.05,
    )


@pytest.mark.asyncio
async def test_bulkhead_concurrency_limiting():
    bulkhead = Bulkhead(name="test_worker_pool", max_concurrent=2)

    # Acquire two slots
    await bulkhead.acquire()
    assert bulkhead.active_count == 1

    await bulkhead.acquire()
    assert bulkhead.active_count == 2

    # Third concurrent acquire exceeds capacity and raises BulkheadExhaustedError
    with pytest.raises(BulkheadExhaustedError, match="maximum 2 concurrent calls"):
        await bulkhead.acquire()

    # Release slot
    bulkhead.release()
    assert bulkhead.active_count == 1

    # Context manager usage
    async with bulkhead:
        assert bulkhead.active_count == 2
    assert bulkhead.active_count == 1

    bulkhead.release()
    assert bulkhead.active_count == 0


@pytest.mark.asyncio
async def test_circuit_breaker_fallback_mode():
    cb = CircuitBreaker(name="test_cb_fallback", failure_threshold=2)

    async def failing_call():
        raise ConnectionResetError("Provider unreachable")

    def fallback_call():
        return "fallback_result_data"

    # Trip the circuit
    for _ in range(2):
        with pytest.raises(ConnectionResetError):
            await cb.call_async(failing_call)

    assert not cb.can_execute()

    # When circuit is open, fallback executes successfully
    result = await cb.call_async(failing_call, fallback_fn=fallback_call)
    assert result == "fallback_result_data"


@pytest.mark.asyncio
async def test_safe_mode_bootstrapper(monkeypatch):
    bootstrapper = SafeModeBootstrapper(allow_safe_mode=True)

    # Mock database failure to trigger safe-mode degradation
    async def mock_db_fail():
        return False

    monkeypatch.setattr(bootstrapper, "verify_database", mock_db_fail)

    status = await bootstrapper.bootstrap()
    assert status.safe_mode is True
    assert "storage_database" in status.degraded_components
    assert status.active_fallbacks.get("database") == "in_memory_sqlite"
    assert status.system_ready is True
