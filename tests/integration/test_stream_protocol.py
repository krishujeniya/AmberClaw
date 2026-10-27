# ruff: noqa: ARG001
"""Integration tests for SSE streaming protocol and chat endpoints."""

from unittest.mock import patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from amberclaw.api.auth import create_access_token
from amberclaw.api.main import app
from amberclaw.api.stream.protocol import (
    done_frame,
    error_frame,
    token_frame,
)


@pytest.fixture
def auth_client():
    token = create_access_token(data={"sub": "stream_tester", "role": "admin"})
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


def test_sse_frame_serialization():
    # Token frame
    tf = token_frame("Hello", index=0)
    sse_str = tf.to_sse()
    assert sse_str.startswith("id: frame_")
    assert "event: token" in sse_str
    assert '"content": "Hello"' in sse_str
    assert sse_str.endswith("\n\n")

    # Error frame
    ef = error_frame("Rate limited", code="RATE_LIMIT")
    sse_err = ef.to_sse()
    assert "event: error" in sse_err
    assert '"code": "RATE_LIMIT"' in sse_err

    # Done frame
    df = done_frame(total_tokens=15, finish_reason="stop")
    sse_done = df.to_sse()
    assert "event: done" in sse_done
    assert '"total_tokens": 15' in sse_done


def test_authenticated_chat_completion(auth_client):
    async def mock_generate(*args, **kwargs):
        return "Simulated completion response"

    with patch("amberclaw.api.v1.chat.llm_router.generate", side_effect=mock_generate):
        response = auth_client.post(
            "/api/v1/chat",
            json={"message": "What is the status of system?"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["reply"] == "Simulated completion response"
        assert data["model"] == "gpt-4o"


def test_authenticated_chat_streaming(auth_client):
    async def mock_generate_stream(*args, **kwargs):
        for token in ["Hello", " ", "from", " ", "AmberClaw", "!"]:
            yield token

    with patch("amberclaw.api.v1.chat.llm_router.generate_stream", side_effect=mock_generate_stream):
        response = auth_client.post(
            "/api/v1/chat/stream",
            json={"message": "Stream hello"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert "text/event-stream" in response.headers.get("content-type", "")

        body = response.text
        # Must contain token chunks and terminal done event
        assert "event: token" in body
        assert "AmberClaw" in body
        assert "event: done" in body
