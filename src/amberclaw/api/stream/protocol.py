# ruff: noqa: S105
"""Standardized SSE Streaming Protocol Definitions for AmberClaw.

Defines chunk types, frame formats, and serialization for token and event streams.
"""

import json
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class StreamChunkType(StrEnum):
    TOKEN = "token"
    THOUGHT = "thought"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    DONE = "done"


class StreamFrame(BaseModel):
    """A single SSE event frame."""

    id: str = Field(default_factory=lambda: f"frame_{uuid.uuid4().hex[:8]}")
    event: StreamChunkType
    data: dict[str, Any] = Field(default_factory=dict)
    retry_ms: int | None = None

    def to_sse(self) -> str:
        """Format the frame as an SSE string (RFC 8895)."""
        payload = json.dumps(self.data, ensure_ascii=False)
        lines = [
            f"id: {self.id}",
            f"event: {self.event.value}",
            f"data: {payload}",
        ]
        if self.retry_ms is not None:
            lines.append(f"retry: {self.retry_ms}")
        return "\n".join(lines) + "\n\n"


def token_frame(content: str, index: int = 0) -> StreamFrame:
    """Create a token chunk frame."""
    return StreamFrame(
        event=StreamChunkType.TOKEN,
        data={"content": content, "index": index},
    )


def error_frame(error_message: str, code: str = "STREAM_ERROR") -> StreamFrame:
    """Create an error chunk frame."""
    return StreamFrame(
        event=StreamChunkType.ERROR,
        data={"error": error_message, "code": code},
    )


def done_frame(total_tokens: int = 0, finish_reason: str = "stop") -> StreamFrame:
    """Create a completion terminal chunk frame."""
    return StreamFrame(
        event=StreamChunkType.DONE,
        data={"finish_reason": finish_reason, "total_tokens": total_tokens},
    )
