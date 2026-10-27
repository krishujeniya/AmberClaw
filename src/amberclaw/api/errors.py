"""Standardized API Error Envelopes and Exception Handlers."""

import uuid
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from amberclaw.security.secret_scanner import SecretScanner


class APIErrorDetail(BaseModel):
    """Detailed error object within API response envelope."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error description")
    request_id: str = Field(..., description="Unique correlation ID for tracing")
    details: dict[str, Any] = Field(default_factory=dict, description="Safe context metadata")


class APIErrorEnvelope(BaseModel):
    """Standardized API response envelope for all error responses."""

    error: APIErrorDetail


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTPExceptions with a structured error envelope."""
    request_id = getattr(request.state, "correlation_id", f"req_{uuid.uuid4().hex[:12]}")
    code = getattr(exc, "code", "HTTP_ERROR")
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        code = "UNAUTHORIZED"
    elif exc.status_code == status.HTTP_403_FORBIDDEN:
        code = "FORBIDDEN"
    elif exc.status_code == status.HTTP_404_NOT_FOUND:
        code = "NOT_FOUND"

    safe_detail = SecretScanner.redact_text(str(exc.detail))

    envelope = APIErrorEnvelope(
        error=APIErrorDetail(
            code=code,
            message=safe_detail,
            request_id=request_id,
        )
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=envelope.model_dump(),
        headers=getattr(exc, "headers", None),
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled server exceptions safely without leaking stack traces or internal secrets."""
    request_id = getattr(request.state, "correlation_id", f"req_{uuid.uuid4().hex[:12]}")

    envelope = APIErrorEnvelope(
        error=APIErrorDetail(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected internal server error occurred.",
            request_id=request_id,
        )
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=envelope.model_dump(),
    )
