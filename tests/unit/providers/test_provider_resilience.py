# ruff: noqa: PLR2004
"""Unit tests for Provider Resilience and CircuitBreaker pattern."""

import asyncio

import pytest

from amberclaw.providers.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    get_circuit_breaker,
)


@pytest.mark.asyncio
async def test_circuit_breaker_normal_closed_execution():
    cb = CircuitBreaker(name="test_provider_normal", failure_threshold=3)
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True

    async def mock_success(val: int) -> int:
        return val * 2

    res = await cb.call_async(mock_success, 10)
    assert res == 20
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_circuit_breaker_trips_to_open():
    cb = CircuitBreaker(name="test_provider_trip", failure_threshold=3, recovery_timeout_s=10.0)

    async def mock_fail():
        raise RuntimeError("Provider 500 downstream failure")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call_async(mock_fail)
        assert cb.state == CircuitState.CLOSED

    # 3rd failure trips circuit
    with pytest.raises(RuntimeError):
        await cb.call_async(mock_fail)

    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False

    # Immediate next call fast-fails with CircuitOpenError
    with pytest.raises(CircuitOpenError) as exc_info:
        await cb.call_async(mock_fail)
    assert "is OPEN" in str(exc_info.value)


@pytest.mark.asyncio
async def test_circuit_breaker_fallback_execution():
    cb = CircuitBreaker(name="test_provider_fallback", failure_threshold=2)

    async def mock_fail():
        raise ConnectionError("Network down")

    async def mock_fallback():
        return "fallback cached reply"

    # Trip the circuit
    for _ in range(2):
        with pytest.raises(ConnectionError):
            await cb.call_async(mock_fail)

    assert cb.state == CircuitState.OPEN

    # Call with fallback
    result = await cb.call_async(mock_fail, fallback_fn=mock_fallback)
    assert result == "fallback cached reply"


@pytest.mark.asyncio
async def test_circuit_breaker_recovery_half_open():
    cb = CircuitBreaker(
        name="test_provider_recovery",
        failure_threshold=2,
        recovery_timeout_s=0.1,  # Short cooldown for test
        half_open_success_threshold=2,
    )

    async def mock_fail():
        raise RuntimeError("boom")

    async def mock_recover():
        return "ok"

    # Trip circuit
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call_async(mock_fail)

    assert cb._state == CircuitState.OPEN

    # Wait for recovery timeout
    await asyncio.sleep(0.15)
    assert cb.state == CircuitState.HALF_OPEN

    # First success in half-open
    await cb.call_async(mock_recover)
    assert cb.state == CircuitState.HALF_OPEN

    # Second success closes circuit
    await cb.call_async(mock_recover)
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True


def test_get_circuit_breaker_singleton():
    cb1 = get_circuit_breaker("model_claude_3")
    cb2 = get_circuit_breaker("model_claude_3")
    assert cb1 is cb2
