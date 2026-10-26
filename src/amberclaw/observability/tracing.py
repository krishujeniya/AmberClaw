"""OpenTelemetry-Compatible Distributed Tracing Engine for AmberClaw AI OS.

Implements W3C Trace Context propagation (traceparent), span lifecycle management,
and OTLP JSON serialization across API -> Bus -> Agent -> Provider -> Tool -> Channel boundaries.
"""

from __future__ import annotations

import contextvars
import re
import secrets
import time
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from enum import StrEnum
from typing import Any

_TRACEPARENT_REGEX = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")

_current_span_var: contextvars.ContextVar[TraceSpan | None] = contextvars.ContextVar(
    "current_trace_span", default=None
)


class SpanKind(StrEnum):
    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class SpanStatusCode(StrEnum):
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


class TraceContext:
    """W3C Trace Context representation."""

    def __init__(
        self,
        trace_id: str | None = None,
        span_id: str | None = None,
        parent_span_id: str | None = None,
        sampled: bool = True,
        correlation_id: str | None = None,
    ):
        self.trace_id = trace_id or secrets.token_hex(16)  # 32 hex chars
        self.span_id = span_id or secrets.token_hex(8)  # 16 hex chars
        self.parent_span_id = parent_span_id
        self.sampled = sampled
        self.correlation_id = correlation_id or self.trace_id

    def to_traceparent(self) -> str:
        flags = "01" if self.sampled else "00"
        return f"00-{self.trace_id}-{self.span_id}-{flags}"

    @classmethod
    def from_traceparent(
        cls, traceparent: str, correlation_id: str | None = None
    ) -> TraceContext | None:
        """Parse W3C traceparent header string."""
        match = _TRACEPARENT_REGEX.match(traceparent.strip().lower())
        if not match:
            return None
        trace_id, parent_span_id, flags = match.groups()
        if trace_id == "0" * 32 or parent_span_id == "0" * 16:
            return None
        sampled = flags == "01"
        return cls(
            trace_id=trace_id,
            span_id=secrets.token_hex(8),
            parent_span_id=parent_span_id,
            sampled=sampled,
            correlation_id=correlation_id or trace_id,
        )

    def inject(self, headers: dict[str, str]) -> None:
        """Inject W3C traceparent and correlation ID into outgoing HTTP/bus carrier."""
        headers["traceparent"] = self.to_traceparent()
        headers["X-Correlation-ID"] = self.correlation_id
        headers["X-Trace-ID"] = self.trace_id

    @classmethod
    def extract(cls, headers: dict[str, Any]) -> TraceContext:
        """Extract W3C traceparent from incoming carrier headers or create a fresh context."""
        # Normalize header keys to lowercase
        norm = {str(k).lower(): str(v) for k, v in headers.items()}
        traceparent = norm.get("traceparent")
        corr_id = norm.get("x-correlation-id") or norm.get("x-request-id")

        if traceparent:
            ctx = cls.from_traceparent(traceparent, correlation_id=corr_id)
            if ctx:
                return ctx

        return cls(correlation_id=corr_id)


class TraceSpan:
    """OpenTelemetry-compatible span recording execution timing, attributes, and events."""

    def __init__(
        self,
        name: str,
        context: TraceContext,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: dict[str, Any] | None = None,
    ):
        self.name = name
        self.context = context
        self.kind = kind
        self.start_time = time.time()
        self.end_time: float | None = None
        self.status = SpanStatusCode.UNSET
        self.status_message: str | None = None
        self.attributes: dict[str, Any] = dict(attributes or {})
        self.events: list[dict[str, Any]] = []

    def set_attribute(self, key: str, value: Any) -> TraceSpan:
        self.attributes[key] = value
        return self

    def add_event(
        self, name: str, attributes: dict[str, Any] | None = None
    ) -> TraceSpan:
        self.events.append(
            {
                "name": name,
                "timestamp": time.time(),
                "attributes": dict(attributes or {}),
            }
        )
        return self

    def set_status(self, code: SpanStatusCode, message: str | None = None) -> TraceSpan:
        self.status = code
        self.status_message = message
        return self

    def record_exception(self, exc: Exception) -> TraceSpan:
        self.set_status(SpanStatusCode.ERROR, str(exc))
        self.add_event(
            "exception",
            {
                "exception.type": exc.__class__.__name__,
                "exception.message": str(exc),
            },
        )
        return self

    def end(self) -> None:
        if self.end_time is None:
            self.end_time = time.time()
            if self.status == SpanStatusCode.UNSET:
                self.status = SpanStatusCode.OK

    @property
    def duration_seconds(self) -> float:
        end = self.end_time or time.time()
        return max(0.0, end - self.start_time)

    def to_otlp_dict(self) -> dict[str, Any]:
        """Convert span to standard OpenTelemetry Collector JSON envelope."""
        return {
            "trace_id": self.context.trace_id,
            "span_id": self.context.span_id,
            "parent_span_id": self.context.parent_span_id,
            "name": self.name,
            "kind": self.kind.value,
            "start_time_unix_nano": int(self.start_time * 1e9),
            "end_time_unix_nano": int((self.end_time or self.start_time) * 1e9),
            "duration_ms": round(self.duration_seconds * 1000, 3),
            "status": {
                "code": self.status.value,
                "message": self.status_message,
            },
            "attributes": self.attributes,
            "events": self.events,
            "correlation_id": self.context.correlation_id,
        }


class Tracer:
    """Manages span creation, contextual propagation, and export buffering."""

    def __init__(self, service_name: str = "amberclaw-os"):
        self.service_name = service_name
        self._finished_spans: list[TraceSpan] = []

    @classmethod
    def get_current_span(cls) -> TraceSpan | None:
        return _current_span_var.get()

    @classmethod
    def get_current_context(cls) -> TraceContext | None:
        span = cls.get_current_span()
        return span.context if span else None

    def start_span(
        self,
        name: str,
        parent_context: TraceContext | None = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: dict[str, Any] | None = None,
    ) -> TraceSpan:
        """Create a new span linked to parent context or current ambient context."""
        active_parent = parent_context or self.get_current_context()
        if active_parent:
            ctx = TraceContext(
                trace_id=active_parent.trace_id,
                span_id=secrets.token_hex(8),
                parent_span_id=active_parent.span_id,
                sampled=active_parent.sampled,
                correlation_id=active_parent.correlation_id,
            )
        else:
            ctx = TraceContext()

        merged_attrs = {"service.name": self.service_name}
        if attributes:
            merged_attrs.update(attributes)

        return TraceSpan(name=name, context=ctx, kind=kind, attributes=merged_attrs)

    @contextmanager
    def start_as_current_span(
        self,
        name: str,
        parent_context: TraceContext | None = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: dict[str, Any] | None = None,
    ) -> Generator[TraceSpan, None, None]:
        span = self.start_span(
            name=name,
            parent_context=parent_context,
            kind=kind,
            attributes=attributes,
        )
        token = _current_span_var.set(span)
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            raise
        finally:
            span.end()
            self._finished_spans.append(span)
            _current_span_var.reset(token)

    @asynccontextmanager
    async def astart_as_current_span(
        self,
        name: str,
        parent_context: TraceContext | None = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: dict[str, Any] | None = None,
    ) -> AsyncGenerator[TraceSpan, None]:
        span = self.start_span(
            name=name,
            parent_context=parent_context,
            kind=kind,
            attributes=attributes,
        )
        token = _current_span_var.set(span)
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            raise
        finally:
            span.end()
            self._finished_spans.append(span)
            _current_span_var.reset(token)

    def get_finished_spans(self) -> list[TraceSpan]:
        return list(self._finished_spans)

    def clear_finished_spans(self) -> None:
        self._finished_spans.clear()


# Global default tracer
global_tracer = Tracer(service_name="amberclaw-os")
