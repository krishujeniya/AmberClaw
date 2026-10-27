# ruff: noqa: S106
"""Prometheus observability metrics collector for AmberClaw AI OS.

Implements cardinality bounding and adaptive telemetry sampling to protect metrics memory.
"""

from __future__ import annotations

import hashlib
import re
from typing import ClassVar

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# Prometheus Telemetry Definitions
HTTP_REQUESTS_TOTAL = Counter(
    "amberclaw_http_requests_total",
    "Total count of HTTP requests handled by AmberClaw API",
    ["method", "endpoint", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "amberclaw_http_request_duration_seconds",
    "HTTP request execution latency in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

LLM_TOKENS_TOTAL = Counter(
    "amberclaw_llm_tokens_total",
    "Total count of LLM tokens consumed",
    ["model", "token_type"],
)

ACTIVE_AGENTS_GAUGE = Gauge(
    "amberclaw_active_agents",
    "Count of registered active agents in persistent store",
)


class CardinalityLimiter:
    """Normalizes high-cardinality path parameters and bounds total unique metric keys."""

    ID_PATTERN = re.compile(
        r"/(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{16,64}|\d+)(?=/|$)"
    )
    _seen_endpoints: ClassVar[set[str]] = set()
    MAX_CARDINALITY = 200

    @classmethod
    def normalize_path(cls, path: str) -> str:
        """Replaces dynamic IDs and UUIDs with `{id}` placeholders."""
        normalized = cls.ID_PATTERN.sub("/:id", path)
        if normalized in cls._seen_endpoints:
            return normalized

        if len(cls._seen_endpoints) >= cls.MAX_CARDINALITY:
            return "/other"

        cls._seen_endpoints.add(normalized)
        return normalized


class TelemetrySampler:
    """Deterministic trace/metrics sampler based on sampling ratio or trace ID hash."""

    def __init__(self, sample_rate: float = 1.0) -> None:
        self.sample_rate = max(0.0, min(1.0, sample_rate))

    def should_sample(self, trace_id: str | None = None) -> bool:
        """Determines whether a trace/metric event should be sampled."""
        if self.sample_rate >= 1.0:
            return True
        if self.sample_rate <= 0.0:
            return False

        if trace_id:
            h = int(hashlib.md5(trace_id.encode("utf-8")).hexdigest()[:8], 16)  # noqa: S324
            return (h % 10000) / 10000.0 < self.sample_rate

        import secrets  # noqa: PLC0415

        return (secrets.randbelow(10000) / 10000.0) < self.sample_rate


default_sampler = TelemetrySampler(sample_rate=1.0)


def record_request_metric(
    method: str, endpoint: str, status_code: int, duration_seconds: float
) -> None:
    """Record HTTP request throughput and latency with cardinality protection."""
    if not default_sampler.should_sample():
        return

    safe_endpoint = CardinalityLimiter.normalize_path(endpoint)
    HTTP_REQUESTS_TOTAL.labels(
        method=method, endpoint=safe_endpoint, status=str(status_code)
    ).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, endpoint=safe_endpoint).observe(
        duration_seconds
    )


def record_token_usage(model: str, prompt_tokens: int, completion_tokens: int) -> None:
    """Record LLM token usage metric."""
    LLM_TOKENS_TOTAL.labels(model=model, token_type="prompt").inc(prompt_tokens)
    LLM_TOKENS_TOTAL.labels(model=model, token_type="completion").inc(completion_tokens)


def get_metrics_payload() -> tuple[bytes, str]:
    """Generate Prometheus exposition text payload and header."""
    return generate_latest(), CONTENT_TYPE_LATEST
