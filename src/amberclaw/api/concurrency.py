"""Optimistic concurrency control and ETag verification for REST API resources."""

import hashlib
import json
from typing import Any

from fastapi import HTTPException, status


def generate_etag(data: Any) -> str:
    """Generate deterministic weak ETag from JSON-serializable data."""
    try:
        content = json.dumps(data, sort_keys=True, default=str)
    except Exception:
        content = str(data)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    return f'W/"{digest}"'


def verify_if_match(if_match_header: str | None, current_etag: str) -> None:
    """Verify If-Match header against the current resource ETag.

    Raises HTTP 412 Precondition Failed if ETags do not match.
    """
    if not if_match_header:
        return

    # Normalize ETags
    clean_header = if_match_header.strip()
    clean_current = current_etag.strip()

    if clean_header == "*":
        return

    if clean_header != clean_current:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=f"Precondition Failed: Resource has been modified. Expected {clean_header}, found {clean_current}",
        )
