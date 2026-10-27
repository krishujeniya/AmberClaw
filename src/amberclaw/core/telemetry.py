import asyncio
import contextlib
import contextvars
import functools
import time
import uuid
from collections.abc import Callable, Iterator
from typing import Any

from loguru import logger

# Thread-local/async-task correlation context
_CORRELATION_ID_CTX: contextvars.ContextVar[str] = contextvars.ContextVar(
    "amberclaw_correlation_id", default=""
)

# Try importing OpenTelemetry API
_OTEL_AVAILABLE = False
try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode

    _OTEL_AVAILABLE = True
except ImportError:
    trace = None  # type: ignore
    Status = None  # type: ignore
    StatusCode = None  # type: ignore


def get_correlation_id() -> str:
    """Get the current correlation ID or generate a new one if not present."""
    cid = _CORRELATION_ID_CTX.get()
    if not cid:
        cid = f"corr_{uuid.uuid4().hex[:12]}"
        _CORRELATION_ID_CTX.set(cid)
    return cid


def set_correlation_id(correlation_id: str) -> None:
    """Set the active correlation ID for the current async task context."""
    _CORRELATION_ID_CTX.set(correlation_id)


def get_tracer(module_name: str = "amberclaw") -> Any:
    """Return an OpenTelemetry tracer if available, else a no-op tracer."""
    if _OTEL_AVAILABLE and trace:
        return trace.get_tracer(module_name)
    return None


@contextlib.contextmanager
def trace_span(
    name: str, attributes: dict[str, Any] | None = None
) -> Iterator[dict[str, Any]]:
    """Context manager for tracing operations with timing and error handling."""
    cid = get_correlation_id()
    attrs = dict(attributes or {})
    attrs["correlation_id"] = cid

    tracer = get_tracer()
    start_time = time.perf_counter()

    if tracer:
        with tracer.start_as_current_span(name, attributes=attrs) as span:
            ctx_data = {"span": span, "attributes": attrs}
            try:
                yield ctx_data
            except Exception as e:
                if Status and StatusCode:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                raise
    else:
        ctx_data = {"span": None, "attributes": attrs}
        try:
            yield ctx_data
        except Exception:
            raise
        finally:
            elapsed = time.perf_counter() - start_time
            logger.debug(f"[Trace: {name}] correlation_id={cid} duration={elapsed:.4f}s")


def traced(name: str | None = None, attributes: dict[str, Any] | None = None) -> Callable:
    """Decorator to trace execution of async or sync functions."""

    def decorator(func: Callable) -> Callable:
        span_name = name or func.__qualname__

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with trace_span(span_name, attributes):
                return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with trace_span(span_name, attributes):
                return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
