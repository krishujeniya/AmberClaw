"""Observability module providing Prometheus metrics and OpenTelemetry distributed tracing."""

from amberclaw.observability.metrics import (
    ACTIVE_AGENTS_GAUGE,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
    LLM_TOKENS_TOTAL,
    get_metrics_payload,
    record_request_metric,
    record_token_usage,
)
from amberclaw.observability.tracing import (
    SpanKind,
    SpanStatusCode,
    TraceContext,
    Tracer,
    TraceSpan,
    global_tracer,
)

__all__ = [
    "ACTIVE_AGENTS_GAUGE",
    "HTTP_REQUESTS_TOTAL",
    "HTTP_REQUEST_DURATION_SECONDS",
    "LLM_TOKENS_TOTAL",
    "SpanKind",
    "SpanStatusCode",
    "TraceContext",
    "TraceSpan",
    "Tracer",
    "get_metrics_payload",
    "global_tracer",
    "record_request_metric",
    "record_token_usage",
]
