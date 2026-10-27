"""Standardized error classification and normalization for LLM providers."""

from __future__ import annotations

import contextlib
import re
from http import HTTPStatus
from typing import Any


class LLMProviderError(Exception):
    """Base class for all normalized LLM provider errors."""

    def __init__(  # noqa: PLR0913
        self,
        message: str,
        provider: str = "",
        model: str = "",
        status_code: int | None = None,
        is_retryable: bool = False,
        raw_error: Exception | str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.model = model
        self.status_code = status_code
        self.is_retryable = is_retryable
        self.raw_error = raw_error

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(message={self.message!r}, "
            f"provider={self.provider!r}, model={self.model!r}, "
            f"status_code={self.status_code}, is_retryable={self.is_retryable})"
        )


class RateLimitError(LLMProviderError):
    """Raised when rate limits or quotas are exceeded (HTTP 429)."""

    def __init__(
        self,
        message: str,
        provider: str = "",
        model: str = "",
        retry_after_s: float | None = None,
        raw_error: Exception | str | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            model=model,
            status_code=HTTPStatus.TOO_MANY_REQUESTS,
            is_retryable=True,
            raw_error=raw_error,
        )
        self.retry_after_s = retry_after_s


class AuthenticationError(LLMProviderError):
    """Raised when credentials or API keys are invalid (HTTP 401/403)."""

    def __init__(
        self,
        message: str,
        provider: str = "",
        model: str = "",
        status_code: int = HTTPStatus.UNAUTHORIZED,
        raw_error: Exception | str | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            model=model,
            status_code=status_code,
            is_retryable=False,
            raw_error=raw_error,
        )


class ContextWindowExceededError(LLMProviderError):
    """Raised when input/output exceeds model context window limit."""

    def __init__(
        self,
        message: str,
        provider: str = "",
        model: str = "",
        raw_error: Exception | str | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            model=model,
            status_code=HTTPStatus.BAD_REQUEST,
            is_retryable=False,
            raw_error=raw_error,
        )


class ProviderTimeoutError(LLMProviderError):
    """Raised when network or gateway timed out (HTTP 408/504 or network timeout)."""

    def __init__(
        self,
        message: str,
        provider: str = "",
        model: str = "",
        raw_error: Exception | str | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            model=model,
            status_code=HTTPStatus.GATEWAY_TIMEOUT,
            is_retryable=True,
            raw_error=raw_error,
        )


class ProviderServerError(LLMProviderError):
    """Raised when provider infrastructure fails (HTTP 500, 502, 503, overloaded)."""

    def __init__(
        self,
        message: str,
        provider: str = "",
        model: str = "",
        status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR,
        raw_error: Exception | str | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            model=model,
            status_code=status_code,
            is_retryable=True,
            raw_error=raw_error,
        )


class ModelNotFoundError(LLMProviderError):
    """Raised when model does not exist or account lacks access (HTTP 404)."""

    def __init__(
        self,
        message: str,
        provider: str = "",
        model: str = "",
        raw_error: Exception | str | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            model=model,
            status_code=HTTPStatus.NOT_FOUND,
            is_retryable=False,
            raw_error=raw_error,
        )


class InvalidRequestError(LLMProviderError):
    """Raised when prompt/arguments are invalid or malformed (HTTP 400)."""

    def __init__(
        self,
        message: str,
        provider: str = "",
        model: str = "",
        raw_error: Exception | str | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            model=model,
            status_code=HTTPStatus.BAD_REQUEST,
            is_retryable=False,
            raw_error=raw_error,
        )


def _extract_status_code(error: Any) -> int | None:
    """Extract numeric HTTP status code from exception if present."""
    if hasattr(error, "status_code") and isinstance(error.status_code, int):
        return error.status_code
    if hasattr(error, "response") and hasattr(error.response, "status_code"):
        return error.response.status_code
    return None


def normalize_provider_error(  # noqa: PLR0911
    error_or_content: Exception | str,
    provider: str = "",
    model: str = "",
) -> LLMProviderError:
    """Normalize any raw provider exception or error text into a structured LLMProviderError."""
    if isinstance(error_or_content, LLMProviderError):
        return error_or_content

    raw_text = str(error_or_content)
    text_lower = raw_text.lower()
    status_code = _extract_status_code(error_or_content)

    # 1. Rate Limiting (429, quota, rate limit)
    if status_code == HTTPStatus.TOO_MANY_REQUESTS or any(
        kw in text_lower
        for kw in [
            "429",
            "rate limit",
            "ratelimit",
            "quota exceeded",
            "too many requests",
        ]
    ):
        retry_after = None
        match = re.search(r"retry[- ]after[:\s]+(\d+(?:\.\d+)?)", text_lower)
        if match:
            with contextlib.suppress(ValueError):
                retry_after = float(match.group(1))
        return RateLimitError(
            message=raw_text,
            provider=provider,
            model=model,
            retry_after_s=retry_after,
            raw_error=error_or_content,
        )

    # 2. Authentication (401, 403, api key, unauthorized)
    if status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN) or any(
        kw in text_lower
        for kw in [
            "401",
            "403",
            "unauthorized",
            "invalid_api_key",
            "invalid api key",
            "authentication",
            "forbidden",
        ]
    ):
        return AuthenticationError(
            message=raw_text,
            provider=provider,
            model=model,
            status_code=status_code or HTTPStatus.UNAUTHORIZED,
            raw_error=error_or_content,
        )

    # 3. Context Window Exceeded
    if any(
        kw in text_lower
        for kw in [
            "context_length_exceeded",
            "context window",
            "maximum context length",
            "token limit exceeded",
            "prompt is too long",
        ]
    ):
        return ContextWindowExceededError(
            message=raw_text,
            provider=provider,
            model=model,
            raw_error=error_or_content,
        )

    # 4. Timeout (408, 504, timed out, deadline exceeded)
    if status_code in (HTTPStatus.REQUEST_TIMEOUT, HTTPStatus.GATEWAY_TIMEOUT) or any(
        kw in text_lower
        for kw in [
            "timeout",
            "timed out",
            "deadline exceeded",
            "readtimeout",
            "connecttimeout",
        ]
    ):
        return ProviderTimeoutError(
            message=raw_text,
            provider=provider,
            model=model,
            raw_error=error_or_content,
        )

    # 5. Model Not Found (404, does not exist)
    if status_code == HTTPStatus.NOT_FOUND or any(
        kw in text_lower
        for kw in ["404", "model not found", "does not exist", "model_not_found"]
    ):
        return ModelNotFoundError(
            message=raw_text,
            provider=provider,
            model=model,
            raw_error=error_or_content,
        )

    # 6. Server / Downstream Error (500, 502, 503, overloaded)
    if (status_code and status_code >= HTTPStatus.INTERNAL_SERVER_ERROR) or any(
        kw in text_lower
        for kw in [
            "500",
            "502",
            "503",
            "server error",
            "overloaded",
            "internal server error",
            "bad gateway",
            "service unavailable",
            "temporarily unavailable",
            "connection refused",
            "connection error",
        ]
    ):
        return ProviderServerError(
            message=raw_text,
            provider=provider,
            model=model,
            status_code=status_code or HTTPStatus.INTERNAL_SERVER_ERROR,
            raw_error=error_or_content,
        )

    # 7. Invalid Request (400, bad request, schema error)
    if status_code == HTTPStatus.BAD_REQUEST or any(
        kw in text_lower
        for kw in [
            "400",
            "invalid_request_error",
            "bad request",
            "unsupported parameter",
        ]
    ):
        return InvalidRequestError(
            message=raw_text,
            provider=provider,
            model=model,
            raw_error=error_or_content,
        )

    # Default generic provider error
    return LLMProviderError(
        message=raw_text,
        provider=provider,
        model=model,
        status_code=status_code,
        is_retryable=False,
        raw_error=error_or_content,
    )
