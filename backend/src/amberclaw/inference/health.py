"""Health monitoring and availability probing for inference model providers."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from enum import StrEnum

from loguru import logger
from pydantic import BaseModel, Field


class ProviderHealthStatus(StrEnum):
    """Health classification for an inference provider endpoint."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class ProviderHealthCheck(BaseModel):
    """Status record resulting from an active provider health probe."""

    provider: str
    status: ProviderHealthStatus = ProviderHealthStatus.UNKNOWN
    latency_ms: float = Field(default=0.0, ge=0.0)
    error: str | None = None
    checked_at: float = Field(default_factory=time.time)


class InferenceHealthMonitor:
    """Monitors live provider response times, tracks outages, and reports health statuses."""

    def __init__(self, latency_threshold_ms: float = 2500.0) -> None:
        self.latency_threshold_ms = latency_threshold_ms
        self._history: dict[str, ProviderHealthCheck] = {}

    async def probe_provider(
        self,
        provider: str,
        probe_fn: Callable[[], Awaitable[bool]] | None = None,
        timeout_seconds: float = 5.0,
    ) -> ProviderHealthCheck:
        """Execute a health probe against a provider, measuring roundtrip latency."""
        start = time.time()
        p_norm = provider.lower()

        if probe_fn is None:
            # Default virtual ping probe
            check = ProviderHealthCheck(
                provider=p_norm,
                status=ProviderHealthStatus.HEALTHY,
                latency_ms=1.0,
            )
            self._history[p_norm] = check
            return check

        try:
            success = await asyncio.wait_for(probe_fn(), timeout=timeout_seconds)
            elapsed_ms = (time.time() - start) * 1000.0
            if success:
                status = (
                    ProviderHealthStatus.DEGRADED
                    if elapsed_ms > self.latency_threshold_ms
                    else ProviderHealthStatus.HEALTHY
                )
                check = ProviderHealthCheck(
                    provider=p_norm,
                    status=status,
                    latency_ms=round(elapsed_ms, 2),
                )
            else:
                check = ProviderHealthCheck(
                    provider=p_norm,
                    status=ProviderHealthStatus.UNAVAILABLE,
                    latency_ms=round(elapsed_ms, 2),
                    error="Probe function returned non-success",
                )
        except TimeoutError:
            elapsed_ms = (time.time() - start) * 1000.0
            check = ProviderHealthCheck(
                provider=p_norm,
                status=ProviderHealthStatus.UNAVAILABLE,
                latency_ms=round(elapsed_ms, 2),
                error=f"Health probe timed out after {timeout_seconds}s",
            )
        except Exception as exc:
            elapsed_ms = (time.time() - start) * 1000.0
            check = ProviderHealthCheck(
                provider=p_norm,
                status=ProviderHealthStatus.UNAVAILABLE,
                latency_ms=round(elapsed_ms, 2),
                error=str(exc),
            )

        self._history[p_norm] = check
        logger.debug(
            "Provider [{}] health: {} ({}ms)",
            p_norm,
            check.status.value,
            check.latency_ms,
        )
        return check

    def get_status(self, provider: str) -> ProviderHealthCheck | None:
        """Retrieve the latest cached health check for a provider."""
        return self._history.get(provider.lower())

    def get_all_statuses(self) -> dict[str, ProviderHealthCheck]:
        """Return all tracked provider health checks."""
        return dict(self._history)
