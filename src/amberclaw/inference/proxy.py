"""Inference network proxy configuration, retry backoff, and circuit breaker protection."""

import time

from loguru import logger
from pydantic import BaseModel, Field


class InferenceProxyConfig(BaseModel):
    """Network proxy parameters and fault tolerance policy."""

    http_proxy: str | None = None
    https_proxy: str | None = None
    no_proxy: str | None = None
    max_retries: int = Field(default=3, ge=0)
    backoff_factor: float = Field(default=1.5, ge=1.0)
    circuit_breaker_failure_threshold: int = Field(default=5, ge=1)
    circuit_breaker_recovery_seconds: float = Field(default=60.0, ge=0.01)


class InferenceProxyManager:
    """Manages outbound proxy routing and provider-level circuit breakers."""

    def __init__(self, config: InferenceProxyConfig | None = None) -> None:
        self.config = config or InferenceProxyConfig()
        self._consecutive_failures: dict[str, int] = {}
        self._tripped_at: dict[str, float] = {}

    def is_available(self, provider: str) -> bool:
        """Check whether the circuit breaker allows calls to this provider."""
        p_norm = provider.lower()
        if p_norm in self._tripped_at:
            elapsed = time.time() - self._tripped_at[p_norm]
            if elapsed < self.config.circuit_breaker_recovery_seconds:
                return False
            # Half-open: allow probe retry
            self._tripped_at.pop(p_norm, None)
            self._consecutive_failures[p_norm] = 0

        failures = self._consecutive_failures.get(p_norm, 0)
        return failures < self.config.circuit_breaker_failure_threshold

    def record_success(self, provider: str) -> None:
        """Reset consecutive failures upon successful inference request."""
        p_norm = provider.lower()
        self._consecutive_failures[p_norm] = 0
        self._tripped_at.pop(p_norm, None)

    def record_failure(self, provider: str) -> None:
        """Increment failure counter and trip breaker if threshold exceeded."""
        p_norm = provider.lower()
        current = self._consecutive_failures.get(p_norm, 0) + 1
        self._consecutive_failures[p_norm] = current

        if current >= self.config.circuit_breaker_failure_threshold:
            self._tripped_at[p_norm] = time.time()
            logger.warning(
                "Circuit breaker tripped for provider '{}' (failures: {})",
                p_norm,
                current,
            )

    def get_proxy_dict(self) -> dict[str, str]:
        """Return proxy mapping suitable for httpx or requests."""
        proxies: dict[str, str] = {}
        if self.config.http_proxy:
            proxies["http://"] = self.config.http_proxy
        if self.config.https_proxy:
            proxies["https://"] = self.config.https_proxy
        return proxies
