# ruff: noqa: PLR2004
"""Unit tests for OpenTelemetry-compatible Distributed Tracing."""

import pytest

from amberclaw.observability.tracing import (
    SpanKind,
    SpanStatusCode,
    TraceContext,
    Tracer,
)


def test_w3c_traceparent_serialization_and_parsing():
    ctx = TraceContext(
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        span_id="00f067aa0ba902b7",
        sampled=True,
    )
    header = ctx.to_traceparent()
    assert header == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

    parsed = TraceContext.from_traceparent(header)
    assert parsed is not None
    assert parsed.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert parsed.parent_span_id == "00f067aa0ba902b7"
    assert parsed.sampled is True


def test_invalid_traceparent_handling():
    # All zeros
    assert (
        TraceContext.from_traceparent(
            "00-00000000000000000000000000000000-0000000000000000-01"
        )
        is None
    )
    # Bad version
    assert TraceContext.from_traceparent("01-abc-def-01") is None
    # Truncated
    assert TraceContext.from_traceparent("00-1234-5678-01") is None


def test_carrier_inject_and_extract():
    ctx = TraceContext(correlation_id="corr_999")
    carrier: dict[str, str] = {}
    ctx.inject(carrier)

    assert "traceparent" in carrier
    assert carrier["X-Correlation-ID"] == "corr_999"
    assert carrier["X-Trace-ID"] == ctx.trace_id

    extracted = TraceContext.extract(carrier)
    assert extracted.trace_id == ctx.trace_id
    assert extracted.parent_span_id == ctx.span_id
    assert extracted.correlation_id == "corr_999"


def test_hierarchical_spans_and_otlp_serialization():
    tracer = Tracer(service_name="test-amberclaw")

    with tracer.start_as_current_span(
        "parent_turn", attributes={"user.id": "usr_1"}
    ) as p_span:
        assert p_span.name == "parent_turn"
        assert p_span.status == SpanStatusCode.UNSET

        # Child span should automatically link to parent
        with tracer.start_as_current_span(
            "tool_call", kind=SpanKind.CLIENT, attributes={"tool.name": "web_search"}
        ) as c_span:
            assert c_span.context.trace_id == p_span.context.trace_id
            assert c_span.context.parent_span_id == p_span.context.span_id

        # Child is now finished
        assert c_span.end_time is not None
        assert c_span.status == SpanStatusCode.OK

    assert p_span.end_time is not None
    assert p_span.status == SpanStatusCode.OK

    spans = tracer.get_finished_spans()
    assert len(spans) == 2

    # Verify OTLP envelope structure
    otlp = p_span.to_otlp_dict()
    assert otlp["name"] == "parent_turn"
    assert otlp["status"]["code"] == "ok"
    assert otlp["attributes"]["user.id"] == "usr_1"
    assert otlp["attributes"]["service.name"] == "test-amberclaw"
    assert otlp["duration_ms"] >= 0.0


@pytest.mark.asyncio
async def test_async_span_and_exception_recording():
    tracer = Tracer(service_name="async-service")

    with pytest.raises(ValueError, match="Operation aborted"):
        async with tracer.astart_as_current_span("failing_async_op") as span:
            span.set_attribute("task.priority", "high")
            raise ValueError("Operation aborted")

    spans = tracer.get_finished_spans()
    assert len(spans) == 1
    failed_span = spans[0]
    assert failed_span.status == SpanStatusCode.ERROR
    assert failed_span.status_message == "Operation aborted"
    assert any(e["name"] == "exception" for e in failed_span.events)
