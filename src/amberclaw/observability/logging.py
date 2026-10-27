# ruff: noqa: DTZ003
"""Structured JSON Logging with In-Flight Secret Redaction and Privacy-Preserving Error Tracking."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from amberclaw.observability.tracing import Tracer
from amberclaw.security.secret_scanner import SecretScanner

_URL_CREDENTIALS_REGEX = re.compile(r"://([^:]+):([^@]+)@")


class RedactingJsonLogFormatter(logging.Formatter):
    """Formats log records as structured JSON Lines while automatically scrubbing secrets in-flight."""

    def __init__(
        self,
        service_name: str = "amberclaw-os",
        redact_entropy: bool = False,
    ):
        super().__init__()
        self.service_name = service_name
        self.redact_entropy = redact_entropy

    def _redact_value(self, val: Any) -> Any:
        if isinstance(val, str):
            redacted = SecretScanner.redact_text(val)
            # Scrub URL passwords (e.g. postgres://user:password@host)
            return _URL_CREDENTIALS_REGEX.sub(r"://\1:[REDACTED]@", redacted)
        if isinstance(val, dict):
            return {k: self._redact_value(v) for k, v in val.items()}
        if isinstance(val, list):
            return [self._redact_value(x) for x in val]
        return val

    def format(self, record: logging.LogRecord) -> str:
        # Resolve active trace context
        trace_ctx = Tracer.get_current_context()
        trace_id = trace_ctx.trace_id if trace_ctx else None
        correlation_id = trace_ctx.correlation_id if trace_ctx else None

        raw_message = record.getMessage()
        sanitized_message = self._redact_value(raw_message)

        payload: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": self.service_name,
            "level": record.levelname,
            "logger": record.name,
            "message": sanitized_message,
        }

        if trace_id:
            payload["trace_id"] = trace_id
        if correlation_id:
            payload["correlation_id"] = correlation_id

        # Extract extra fields
        standard_attrs = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
        }
        extras = {
            k: self._redact_value(v)
            for k, v in record.__dict__.items()
            if k not in standard_attrs and not k.startswith("_")
        }
        if extras:
            payload["extra"] = extras

        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            payload["exception"] = self._redact_value(exc_text)

        return json.dumps(payload, ensure_ascii=False)


class PrivacyPreservingErrorTracker:
    """Sanitizes runtime errors and tracebacks to prevent information disclosure."""

    @classmethod
    def sanitize_error(
        cls,
        error: Exception | str,
        workspace_root: Path | str | None = None,
    ) -> dict[str, Any]:
        """Produce a sanitized error dictionary free of filesystem paths and credentials."""
        raw_msg = str(error)
        err_type = error.__class__.__name__ if isinstance(error, Exception) else "Error"

        # 1. Redact secrets
        clean_msg = SecretScanner.redact_text(raw_msg)
        clean_msg = _URL_CREDENTIALS_REGEX.sub(r"://\1:[REDACTED]@", clean_msg)

        # 2. Scrub absolute host paths
        if workspace_root:
            ws_str = str(Path(workspace_root).resolve())
            clean_msg = clean_msg.replace(ws_str, "[WORKSPACE]")

        # Mask home directory paths
        clean_msg = re.sub(r"/(?:home|Users)/[a-zA-Z0-9_\-]+", "[HOME]", clean_msg)

        # Trace context
        ctx = Tracer.get_current_context()

        return {
            "error_type": err_type,
            "message": clean_msg,
            "trace_id": ctx.trace_id if ctx else None,
            "correlation_id": ctx.correlation_id if ctx else None,
            "sanitized": clean_msg != raw_msg,
        }
