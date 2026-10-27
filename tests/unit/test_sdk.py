# ruff: noqa: S106, PLR2004
"""Unit tests for the AmberClaw Python Client SDK."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from amberclaw.sdk.client import (
    AmberClawClient,
    AsyncAmberClawClient,
    _parse_error_response,
)
from amberclaw.sdk.exceptions import (
    AmberClawAPIError,
    AmberClawAuthError,
)


def test_sdk_headers_initialization():
    # Bearer token
    client_jwt = AmberClawClient(base_url="http://127.0.0.1:8000", token="jwt_test_token")
    headers = client_jwt._build_headers()
    assert headers["Authorization"] == "Bearer jwt_test_token"
    assert "X-API-Key" not in headers

    # API key
    client_key = AmberClawClient(base_url="http://127.0.0.1:8000", api_key="ak_test_key")
    headers_key = client_key._build_headers()
    assert headers_key["X-API-Key"] == "ak_test_key"
    assert "Authorization" not in headers_key


def test_parse_error_response_structured_envelope():
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {
        "error": {
            "code": "INVALID_PARAMS",
            "message": "Missing prompt argument",
            "request_id": "req_abc123",
        }
    }
    err = _parse_error_response(mock_resp)
    assert isinstance(err, AmberClawAPIError)
    assert err.code == "INVALID_PARAMS"
    assert err.message == "Missing prompt argument"
    assert err.request_id == "req_abc123"
    assert err.status_code == 400


def test_sync_client_health_and_metrics():
    client = AmberClawClient(base_url="http://127.0.0.1:8000")

    # Mock health
    mock_health = MagicMock()
    mock_health.is_error = False
    mock_health.json.return_value = {"status": "ok", "version": "2026.0.1"}

    # Mock metrics
    mock_metrics = MagicMock()
    mock_metrics.is_error = False
    mock_metrics.text = "# HELP http_requests_total\nhttp_requests_total 42"

    with patch.object(client._client, "get", side_effect=[mock_health, mock_metrics]):
        health_data = client.health()
        assert health_data["status"] == "ok"

        metrics_data = client.get_metrics()
        assert "http_requests_total" in metrics_data


def test_sync_client_chat():
    client = AmberClawClient(base_url="http://127.0.0.1:8000", api_key="valid_key")
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.is_error = False
    mock_res.json.return_value = {"reply": "Hello there!", "model": "gpt-4o"}

    with patch.object(client._client, "post", return_value=mock_res) as mock_post:
        reply = client.chat(message="Hello", model="gpt-4o", session_id="ses_1")
        assert reply["reply"] == "Hello there!"
        mock_post.assert_called_once_with(
            "/api/v1/chat",
            json={"message": "Hello", "model": "gpt-4o", "session_id": "ses_1"},
        )


def test_sync_client_chat_stream():
    client = AmberClawClient(base_url="http://127.0.0.1:8000", api_key="valid_key")
    sse_chunks = [
        'event: token\ndata: {"content": "Hello", "index": 0}\n\n',
        'event: token\ndata: {"content": " world", "index": 1}\n\n',
        'event: done\ndata: {"finish_reason": "stop", "total_tokens": 2}\n\n',
    ]

    mock_stream_response = MagicMock()
    mock_stream_response.status_code = 200
    mock_stream_response.is_error = False
    mock_stream_response.iter_text.return_value = iter(sse_chunks)

    with patch.object(client._client, "stream") as mock_stream:
        mock_stream.return_value.__enter__.return_value = mock_stream_response
        events = list(client.chat_stream("Hello"))

        assert len(events) == 3
        assert events[0]["event"] == "token"
        assert events[0]["data"]["content"] == "Hello"
        assert events[1]["data"]["content"] == " world"
        assert events[2]["event"] == "done"
        assert events[2]["data"]["finish_reason"] == "stop"


@pytest.mark.asyncio
async def test_async_client_chat_and_stream():
    async with AsyncAmberClawClient(base_url="http://127.0.0.1:8000", token="token_123") as client:
        # Mock chat
        mock_chat_res = MagicMock()
        mock_chat_res.status_code = 200
        mock_chat_res.is_error = False
        mock_chat_res.json.return_value = {"reply": "Async reply", "model": "gpt-4o"}

        with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_chat_res
            reply = await client.chat("Hi async")
            assert reply["reply"] == "Async reply"

        # Mock stream
        sse_chunks = [
            'event: token\ndata: {"content": "Async", "index": 0}\n\n',
            'event: done\ndata: {"total_tokens": 1}\n\n',
        ]

        async def async_iter():
            for c in sse_chunks:
                yield c

        mock_stream_response = MagicMock()
        mock_stream_response.status_code = 200
        mock_stream_response.is_error = False
        mock_stream_response.aiter_text = async_iter

        with patch.object(client._client, "stream") as mock_stream:
            mock_stream.return_value.__aenter__.return_value = mock_stream_response
            received = []
            async for ev in client.chat_stream("Stream async"):
                received.append(ev)

            assert len(received) == 2
            assert received[0]["data"]["content"] == "Async"
            assert received[1]["event"] == "done"


@pytest.mark.asyncio
async def test_async_client_auth_error_handling():
    async with AsyncAmberClawClient(base_url="http://127.0.0.1:8000", token="bad_token") as client:
        mock_res = MagicMock()
        mock_res.status_code = 401
        mock_res.is_error = True

        with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_res
            with pytest.raises(AmberClawAuthError):
                await client.chat("Hello")
