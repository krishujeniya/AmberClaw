# ruff: noqa: S106
"""Prometheus observability metrics collector for AmberClaw AI OS."""

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


def record_request_metric(
    method: str, endpoint: str, status_code: int, duration_seconds: float
) -> None:
    """Record HTTP request throughput and latency."""
    HTTP_REQUESTS_TOTAL.labels(
        method=method, endpoint=endpoint, status=str(status_code)
    ).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, endpoint=endpoint).observe(
        duration_seconds
    )


def record_token_usage(model: str, prompt_tokens: int, completion_tokens: int) -> None:
    """Record LLM token usage metric."""
    LLM_TOKENS_TOTAL.labels(model=model, token_type="prompt").inc(prompt_tokens)
    LLM_TOKENS_TOTAL.labels(model=model, token_type="completion").inc(completion_tokens)


def get_metrics_payload() -> tuple[bytes, str]:
    """Generate Prometheus exposition text payload and header."""
    return generate_latest(), CONTENT_TYPE_LATEST
