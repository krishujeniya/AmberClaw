"""API Security and Abuse Control Middlewares for AmberClaw.

Implements payload size limits (HTTP 413) and per-client rate limiting (HTTP 429).
"""

import asyncio
import time
from collections import defaultdict
from typing import ClassVar

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

MAX_BODY_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB maximum request payload


class IdempotencyRecord:
    """Cached response metadata and body for an idempotent request."""

    def __init__(
        self,
        status_code: int,
        headers: dict[str, str],
        body: bytes,
        timestamp: float,
    ):
        self.status_code = status_code
        self.headers = headers
        self.body = body
        self.timestamp = timestamp


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Idempotency middleware preventing duplicate operations on mutating HTTP methods."""

    def __init__(self, app, ttl_seconds: int = 86400):
        super().__init__(app)
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, IdempotencyRecord] = {}

    def _get_cache_key(self, request: Request, key: str) -> str:
        auth = request.headers.get("authorization", "anon")
        return f"{auth}:{request.method}:{request.url.path}:{key}"

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        idempotency_key = request.headers.get("x-idempotency-key")
        if not idempotency_key or request.method not in {
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
        }:
            return await call_next(request)

        cache_key = self._get_cache_key(request, idempotency_key)
        now = time.time()

        # Check cache for existing completed response
        record = self._cache.get(cache_key)
        if record and (now - record.timestamp < self.ttl_seconds):
            headers = dict(record.headers)
            headers["X-Idempotency-Replayed"] = "true"
            headers["X-Cache"] = "HIT"
            return Response(
                content=record.body,
                status_code=record.status_code,
                headers=headers,
                media_type=headers.get("content-type", "application/json"),
            )

        response = await call_next(request)

        # Cache successful or client-error responses (avoid caching transient 5xx server errors)
        if response.status_code < status.HTTP_500_INTERNAL_SERVER_ERROR:
            body_chunks = [chunk async for chunk in response.body_iterator]
            body = b"".join(body_chunks)
            headers = dict(response.headers)
            # Remove transfer-encoding if present since body is buffered
            headers.pop("transfer-encoding", None)
            headers.pop("content-length", None)
            self._cache[cache_key] = IdempotencyRecord(
                status_code=response.status_code,
                headers=headers,
                body=body,
                timestamp=now,
            )
            return Response(
                content=body,
                status_code=response.status_code,
                headers=headers,
                media_type=response.media_type,
            )

        return response


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """Enforces maximum request execution timeout with 504 Gateway Timeout envelope."""

    def __init__(self, app, timeout_seconds: float = 30.0):
        super().__init__(app)
        self.timeout_seconds = timeout_seconds

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Exclude streaming or WebSocket routes
        if request.url.path.startswith("/api/v1/stream"):
            return await call_next(request)

        try:
            return await asyncio.wait_for(
                call_next(request), timeout=self.timeout_seconds
            )
        except TimeoutError:
            return JSONResponse(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                content={
                    "error": "Gateway Timeout",
                    "message": f"Request processing exceeded deadline of {self.timeout_seconds}s.",
                },
            )


class RequestBodyLimitMiddleware(BaseHTTPMiddleware):
    """Middleware enforcing a strict maximum HTTP request body size."""

    def __init__(self, app, max_bytes: int = MAX_BODY_SIZE_BYTES):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                if length > self.max_bytes:
                    return JSONResponse(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        content={
                            "error": "Payload Too Large",
                            "message": f"Request body exceeds maximum allowed limit of {self.max_bytes // (1024 * 1024)} MB",
                        },
                    )
            except ValueError:
                pass

        return await call_next(request)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiting middleware per client IP or auth token."""

    _instances: ClassVar[list["RateLimiterMiddleware"]] = []

    def __init__(self, app, max_requests: int = 10, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # Mapping key -> list of request timestamps
        self._requests: dict[str, list[float]] = defaultdict(list)
        RateLimiterMiddleware._instances.append(self)

    @classmethod
    def reset_all(cls) -> None:
        """Reset state across all rate limiter instances (useful for test isolation)."""
        for instance in cls._instances:
            instance.reset()

    def reset(self) -> None:
        """Reset rate limiter state for this instance."""
        self._requests.clear()

    def _get_client_identifier(self, request: Request) -> str:
        # Check Authorization header first if present
        auth = request.headers.get("authorization")
        if auth:
            return f"auth:{auth.strip()}"
        # Fall back to client IP address
        if request.client:
            return f"ip:{request.client.host}"
        return "ip:127.0.0.1"

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Exclude health checks, metrics, and static endpoints from rate limits
        if request.url.path in {
            "/health",
            "/metrics",
            "/docs",
            "/openapi.json",
            "/favicon.ico",
        }:
            return await call_next(request)

        now = time.time()
        client_key = self._get_client_identifier(request)
        cutoff = now - self.window_seconds

        # Clean old timestamps
        timestamps = [t for t in self._requests[client_key] if t > cutoff]
        self._requests[client_key] = timestamps

        if len(timestamps) >= self.max_requests:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(self.window_seconds)},
                content={
                    "error": "Too Many Requests",
                    "message": f"Rate limit exceeded ({self.max_requests} req / {self.window_seconds}s). Please slow down.",
                },
            )

        self._requests[client_key].append(now)
        return await call_next(request)


class APIDeprecationMiddleware(BaseHTTPMiddleware):
    """Injects RFC 8594 standard Deprecation and Sunset headers on deprecated endpoints."""

    DEFAULT_DEPRECATED_PREFIXES: ClassVar[tuple[str, ...]] = (
        "/api/v0/",
        "/api/legacy/",
    )

    def __init__(
        self,
        app,
        deprecated_prefixes: tuple[str, ...] | None = None,
        sunset_date: str = "Wed, 11 Nov 2026 00:00:00 GMT",
    ) -> None:
        super().__init__(app)
        self.deprecated_prefixes = (
            deprecated_prefixes or self.DEFAULT_DEPRECATED_PREFIXES
        )
        self.sunset_date = sunset_date

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        path = request.url.path

        if any(path.startswith(prefix) for prefix in self.deprecated_prefixes):
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = self.sunset_date
            response.headers["Link"] = '</docs/deprecations>; rel="sunset"'
            response.headers["Warning"] = (
                '299 - "This endpoint is deprecated and subject to a sunset window."'
            )

        return response
