"""Server-Sent Events (SSE) Stream Helpers for FastAPI Responses."""

from collections.abc import AsyncGenerator

from fastapi.responses import StreamingResponse

from amberclaw.api.stream.protocol import (
    StreamChunkType,
    StreamFrame,
    done_frame,
    error_frame,
    token_frame,
)


def create_sse_response(generator: AsyncGenerator[str, None]) -> StreamingResponse:
    """Wrap an async generator of formatted SSE frame strings into a FastAPI StreamingResponse."""
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


__all__ = [
    "StreamChunkType",
    "StreamFrame",
    "create_sse_response",
    "done_frame",
    "error_frame",
    "token_frame",
]
