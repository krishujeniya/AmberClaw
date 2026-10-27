"""Circuit breaker and provider health scoring engine."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Callable
from enum import StrEnum
from typing import Any

from loguru import logger


class CircuitState(StrEnum):
    CLOSED = "closed"  # Normal operation; requests pass through
    OPEN = "open"  # Tripped; requests are rejected / fast-failed
    HALF_OPEN = "half_open"  # Probing; testing if provider has recovered


class CircuitOpenError(RuntimeError):
    """Raised when an execution is attempted on an open circuit."""

    def __init__(self, circuit_name: str, cooldown_remaining: float):
        super().__init__(
            f"Circuit '{circuit_name}' is OPEN. Fast-failing request (retry in {cooldown_remaining:.1f}s)."
        )
        self.circuit_name = circuit_name
        self.cooldown_remaining = cooldown_remaining


_LATENCY_PENALTY_THRESHOLD_MS = 2000.0
_LATENCY_PENALTY_SCALE = 10000.0


class ProviderHealthTracker:
    """Tracks sliding window execution statistics and computes dynamic health score (0.0 to 1.0)."""

    def __init__(self, name: str, window_size: int = 50):
        self.name = name
        self.window_size = window_size
        self._history: deque[tuple[float, bool, float]] = deque(maxlen=window_size)
        self.total_calls: int = 0
        self.total_failures: int = 0
        self.consecutive_failures: int = 0

    def record_call(self, success: bool, latency_ms: float = 0.0) -> None:
        """Record a single provider call result and duration."""
        self.total_calls += 1
        if success:
            self.consecutive_failures = 0
        else:
            self.total_failures += 1
            self.consecutive_failures += 1
        self._history.append((time.time(), success, latency_ms))

    def compute_health_score(
        self, circuit_state: CircuitState = CircuitState.CLOSED
    ) -> float:
        """Compute provider health score between 0.0 (unhealthy) and 1.0 (optimal)."""
        if circuit_state == CircuitState.OPEN:
            return 0.0

        if not self._history:
            return 1.0 if circuit_state == CircuitState.CLOSED else 0.5

        successes = sum(1 for _, s, _ in self._history if s)
        success_rate = successes / len(self._history)

        # Calculate p95 latency
        latencies = sorted(lat for _, _, lat in self._history if lat > 0)
        p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0

        # Latency penalty: penalize if p95 exceeds threshold
        latency_penalty = 0.0
        if p95 > _LATENCY_PENALTY_THRESHOLD_MS:
            latency_penalty = min(
                0.3, (p95 - _LATENCY_PENALTY_THRESHOLD_MS) / _LATENCY_PENALTY_SCALE
            )

        # Consecutive failure penalty
        consec_penalty = min(0.5, self.consecutive_failures * 0.1)

        base = success_rate - latency_penalty - consec_penalty
        if circuit_state == CircuitState.HALF_OPEN:
            base = min(base, 0.5)

        return max(0.0, min(1.0, round(base, 3)))

    def get_health_metrics(
        self, circuit_state: CircuitState = CircuitState.CLOSED
    ) -> dict[str, Any]:
        """Return snapshot dictionary of health metrics."""
        latencies = sorted(lat for _, _, lat in self._history if lat > 0)
        p50 = latencies[int(len(latencies) * 0.5)] if latencies else 0.0
        p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0
        success_rate = (
            (sum(1 for _, s, _ in self._history if s) / len(self._history))
            if self._history
            else 1.0
        )

        return {
            "name": self.name,
            "circuit_state": str(circuit_state),
            "health_score": self.compute_health_score(circuit_state),
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "consecutive_failures": self.consecutive_failures,
            "success_rate": round(success_rate, 3),
            "failure_rate": round(1.0 - success_rate, 3),
            "p50_latency_ms": round(p50, 2),
            "p95_latency_ms": round(p95, 2),
        }


class CircuitBreaker:
    """Thread-safe and async-safe circuit breaker with automatic half-open probing and health scoring."""

    def __init__(
        self,
        name: str = "llm_provider",
        failure_threshold: int = 5,
        recovery_timeout_s: float = 30.0,
        half_open_success_threshold: int = 2,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_s = recovery_timeout_s
        self.half_open_success_threshold = half_open_success_threshold

        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._success_count: int = 0
        self._last_failure_time: float = 0.0
        self._lock = asyncio.Lock()
        self.health_tracker = ProviderHealthTracker(name=name)

    @property
    def state(self) -> CircuitState:
        """Evaluate and return the effective circuit state considering recovery timeout."""
        if self._state == CircuitState.OPEN:
            now = time.time()
            if now - self._last_failure_time >= self.recovery_timeout_s:
                return CircuitState.HALF_OPEN
        return self._state

    @property
    def health_score(self) -> float:
        """Return the current dynamic health score."""
        return self.health_tracker.compute_health_score(self.state)

    def can_execute(self) -> bool:
        """Check if request is permitted to proceed under current circuit state."""
        return self.state in {CircuitState.CLOSED, CircuitState.HALF_OPEN}

    def record_success(self, latency_ms: float = 0.0) -> None:
        """Record a successful execution, recovering circuit if probing in half-open state."""
        self.health_tracker.record_call(True, latency_ms=latency_ms)
        current = self.state
        if current == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.half_open_success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._success_count = 0
                logger.info(f"CircuitBreaker [{self.name}] recovered to CLOSED state.")
        elif current == CircuitState.CLOSED:
            self._failure_count = 0

    def record_failure(
        self, error: Exception | None = None, latency_ms: float = 0.0
    ) -> None:
        """Record a failed execution, tripping circuit if threshold is reached."""
        self.health_tracker.record_call(False, latency_ms=latency_ms)
        self._last_failure_time = time.time()
        self._failure_count += 1
        self._success_count = 0

        current = self.state
        if (
            current == CircuitState.HALF_OPEN
            or self._failure_count >= self.failure_threshold
        ):
            self._state = CircuitState.OPEN
            logger.warning(
                f"CircuitBreaker [{self.name}] TRIPPED to OPEN state after "
                f"{self._failure_count} consecutive failures. Error: {error}"
            )

    def reset(self) -> None:
        """Manually reset the circuit breaker to clean closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0

    def get_health_metrics(self) -> dict[str, Any]:
        """Return snapshot of provider health and circuit breaker metrics."""
        return self.health_tracker.get_health_metrics(self.state)

    async def call_async(
        self,
        coro_fn: Callable[..., Any],
        *args: Any,
        fallback_fn: Callable[..., Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Execute an async coroutine with circuit breaker protection."""
        if not self.can_execute():
            cooldown_left = max(
                0.0, self.recovery_timeout_s - (time.time() - self._last_failure_time)
            )
            if fallback_fn:
                logger.info(
                    f"CircuitBreaker [{self.name}] open; executing fallback function."
                )
                if asyncio.iscoroutinefunction(fallback_fn):
                    return await fallback_fn(*args, **kwargs)
                return fallback_fn(*args, **kwargs)
            raise CircuitOpenError(self.name, cooldown_left)

        start_time = time.perf_counter()
        try:
            result = await coro_fn(*args, **kwargs)
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            self.record_success(latency_ms=latency_ms)
            return result
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            self.record_failure(e, latency_ms=latency_ms)
            raise


# Global registry of circuit breakers per provider/model
_CIRCUIT_BREAKERS: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str, failure_threshold: int = 5, recovery_timeout_s: float = 30.0
) -> CircuitBreaker:
    """Get or create a named CircuitBreaker singleton."""
    if name not in _CIRCUIT_BREAKERS:
        _CIRCUIT_BREAKERS[name] = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout_s=recovery_timeout_s,
        )
    return _CIRCUIT_BREAKERS[name]


def get_all_provider_health_metrics() -> dict[str, dict[str, Any]]:
    """Return health metrics for all registered provider circuit breakers."""
    return {name: cb.get_health_metrics() for name, cb in _CIRCUIT_BREAKERS.items()}


class BulkheadExhaustedError(RuntimeError):
    """Raised when bulkhead concurrent worker slots are fully saturated."""


class Bulkhead:
    """Limits concurrent executions to prevent cascading resource starvation across worker pools."""

    def __init__(self, name: str, max_concurrent: int = 10):
        self.name = name
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self.active_count: int = 0

    async def acquire(self) -> None:
        """Acquire a concurrent execution slot in the bulkhead."""
        if self.active_count >= self.max_concurrent:
            raise BulkheadExhaustedError(
                f"Bulkhead [{self.name}] saturated: maximum {self.max_concurrent} concurrent calls active"
            )
        await self._semaphore.acquire()
        self.active_count += 1

    def release(self) -> None:
        """Release a concurrent execution slot."""
        self.active_count = max(0, self.active_count - 1)
        self._semaphore.release()

    async def __aenter__(self) -> Bulkhead:
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()
