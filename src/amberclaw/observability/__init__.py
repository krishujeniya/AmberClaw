"""Observability module providing Prometheus metrics, OpenTelemetry tracing, redacting logging, and SLO alerts."""

from amberclaw.observability.alerts import (
    AlertNotification,
    AuditHealthReport,
    AuditLogHealthChecker,
    SLOMonitor,
)
from amberclaw.observability.logging import (
    PrivacyPreservingErrorTracker,
    RedactingJsonLogFormatter,
)
from amberclaw.observability.metrics import (
    ACTIVE_AGENTS_GAUGE,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
    LLM_TOKENS_TOTAL,
    get_metrics_payload,
    record_request_metric,
    record_token_usage,
)
from amberclaw.observability.run_tracer import (
    RunReplayFixture,
    RunReconstructor,
    RunTimelineEvent,
    RunTraceContext,
    TraceRedactionPolicy,
    bound_run_context,
    get_current_run_context,
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
    "AlertNotification",
    "AuditHealthReport",
    "AuditLogHealthChecker",
    "PrivacyPreservingErrorTracker",
    "RedactingJsonLogFormatter",
    "RunReplayFixture",
    "RunReconstructor",
    "RunTimelineEvent",
    "RunTraceContext",
    "SLOMonitor",
    "SpanKind",
    "SpanStatusCode",
    "TraceContext",
    "TraceRedactionPolicy",
    "TraceSpan",
    "Tracer",
    "bound_run_context",
    "get_current_run_context",
    "get_metrics_payload",
    "global_tracer",
    "record_request_metric",
    "record_token_usage",
]
