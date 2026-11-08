"""Offline regressions for task, response, and exception protocol boundaries."""

import asyncio
import importlib.util
import inspect
import sys
from collections.abc import Callable
from unittest.mock import Mock

import pytest
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from amberclaw.api import auth
from amberclaw.api.errors import http_exception_handler
from amberclaw.api.middleware import IdempotencyMiddleware
from amberclaw.core import telemetry
from amberclaw.core.concurrency import StructuredTaskGroup


@pytest.mark.asyncio
async def test_structured_group_accepts_future_awaitables() -> None:
    future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
    future.set_result("complete")
    async with StructuredTaskGroup("future") as group:
        task = group.create_task(future)
    assert task.result() == "complete"
    assert group.tasks == [task]


def idempotent_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/operation",
            "query_string": b"",
            "headers": [(b"x-idempotency-key", b"fixture")],
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response_factory",
    [
        lambda: Response("café!"),
        lambda: StreamingResponse(iter(["café", memoryview(b"!")])),
    ],
)
async def test_idempotency_buffers_all_response_content_types(
    response_factory: Callable[[], Response],
) -> None:
    middleware = IdempotencyMiddleware(FastAPI())
    calls = 0

    async def call_next(_: Request) -> Response:
        nonlocal calls
        calls += 1
        return response_factory()

    first = await middleware.dispatch(idempotent_request(), call_next)
    second = await middleware.dispatch(idempotent_request(), call_next)
    assert first.body == "café!".encode()
    assert second.body == first.body
    assert second.headers["X-Idempotency-Replayed"] == "true"
    assert calls == 1


@pytest.mark.asyncio
async def test_idempotency_preserves_original_background_cleanup_only_once() -> None:
    middleware = IdempotencyMiddleware(FastAPI())
    cleanup = Mock()

    async def call_next(_: Request) -> Response:
        return StreamingResponse(
            iter([b"complete"]), background=BackgroundTask(cleanup)
        )

    first = await middleware.dispatch(idempotent_request(), call_next)
    assert first.background is not None
    await first.background()
    replay = await middleware.dispatch(idempotent_request(), call_next)
    assert replay.background is None
    cleanup.assert_called_once_with()


@pytest.mark.asyncio
async def test_http_handler_accepts_registered_exception_protocol() -> None:
    response = await http_exception_handler(
        idempotent_request(), ValueError("private failure")
    )
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert b"private failure" not in response.body


def test_access_token_creation_enforces_string_return_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        auth.jwt, "encode", lambda *_args, **_kwargs: b"invalid encoder output"
    )
    with pytest.raises(TypeError, match="JWT encoder"):
        auth.create_access_token({"sub": "offline"})


@pytest.mark.asyncio
async def test_task_cancelled_before_start_closes_native_coroutine() -> None:
    async def worker() -> str:
        return "unused"

    coroutine = worker()
    try:
        async with StructuredTaskGroup("early-cancel") as group:
            task = group.create_task(coroutine)
            task.cancel()
        assert inspect.getcoroutinestate(coroutine) == inspect.CORO_CLOSED
    finally:
        coroutine.close()


def test_telemetry_import_and_error_context_work_without_optional_sdk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert telemetry.__file__ is not None
    spec = importlib.util.spec_from_file_location(
        "amberclaw_telemetry_without_sdk", telemetry.__file__
    )
    assert spec is not None
    assert spec.loader is not None
    isolated = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "opentelemetry", None)
    spec.loader.exec_module(isolated)
    assert isolated.get_tracer() is None
    with (
        pytest.raises(ValueError, match="offline failure"),
        isolated.trace_span("offline") as context,
    ):
        assert context["span"] is None
        raise ValueError("offline failure")
