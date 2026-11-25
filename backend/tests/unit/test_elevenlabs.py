# ruff: noqa: PLR2004
import asyncio
import base64
import json
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from amberclaw.voice.elevenlabs import ElevenLabsConfig, ElevenLabsTTS


def test_elevenlabs_config_defaults() -> None:
    config = ElevenLabsConfig(api_key="test-key")
    assert config.api_key == "test-key"
    assert config.voice_id == "pNInz6obpgmqMArAY74m"
    assert config.model_id == "eleven_monolingual_v1"
    assert config.output_format == "mp3_44100_128"


@pytest.mark.asyncio
async def test_stream_tts_http() -> None:
    config = ElevenLabsConfig(api_key="test-key-http")
    client = ElevenLabsTTS(config)

    # Mock response object for HTTP streaming
    mock_response = MagicMock()
    mock_response.status_code = 200

    async def mock_aiter_bytes() -> AsyncIterator[bytes]:
        yield b"audio-chunk-1"
        yield b"audio-chunk-2"

    mock_response.aiter_bytes = mock_aiter_bytes

    # Mock context manager returned by httpx.AsyncClient.stream
    class MockStreamContext:
        async def __aenter__(self) -> Any:
            return mock_response

        async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            pass

    with patch(
        "httpx.AsyncClient.stream", return_value=MockStreamContext()
    ) as mock_stream:
        chunks = []
        async for chunk in client.stream_tts_http("hello world"):
            chunks.append(chunk)

        assert chunks == [b"audio-chunk-1", b"audio-chunk-2"]

        # Verify correct HTTP parameters
        mock_stream.assert_called_once()
        call_args = mock_stream.call_args

        # URL verification
        assert "pNInz6obpgmqMArAY74m/stream" in call_args[0][1]

        # Headers/payload validation
        headers = call_args[1]["headers"]
        assert headers["xi-api-key"] == "test-key-http"

        json_data = call_args[1]["json"]
        assert json_data["text"] == "hello world"
        assert json_data["model_id"] == "eleven_monolingual_v1"


@pytest.mark.asyncio
async def test_stream_tts_websocket() -> None:
    config = ElevenLabsConfig(api_key="test-key-ws")
    client = ElevenLabsTTS(config)

    # 1. Setup mock messages that ElevenLabs server sends back (base64 JSON frames)
    mock_audio_1 = base64.b64encode(b"decoded-audio-1").decode("utf-8")
    mock_audio_2 = base64.b64encode(b"decoded-audio-2").decode("utf-8")

    server_frames = [
        json.dumps({"audio": mock_audio_1, "isFinal": False}),
        json.dumps({"audio": mock_audio_2, "isFinal": True}),
    ]

    # 2. Setup mock WebSocket client
    mock_ws = AsyncMock()

    # We will simulate server sending frames
    class MockWSAsyncIterator:
        def __init__(self) -> None:
            self.index = 0

        def __aiter__(self) -> "MockWSAsyncIterator":
            return self

        async def __anext__(self) -> str:
            await asyncio.sleep(0.01)
            if self.index < len(server_frames):
                frame = server_frames[self.index]
                self.index += 1
                return frame
            raise StopAsyncIteration

    mock_ws.__aiter__.side_effect = MockWSAsyncIterator

    # Context manager mock for websockets.connect
    class MockWSContext:
        async def __aenter__(self) -> AsyncMock:
            return mock_ws

        async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            pass

    # Async text iterator to stream text tokens to the WebSocket
    async def text_stream() -> AsyncIterator[str]:
        yield "token1 "
        yield "token2"

    with patch("websockets.connect", return_value=MockWSContext()) as mock_connect:
        audio_chunks = []
        async for chunk in client.stream_tts_websocket(text_stream()):
            audio_chunks.append(chunk)

        # Assert yielded audio chunks decode properly
        assert audio_chunks == [b"decoded-audio-1", b"decoded-audio-2"]

        # Assert correct WS URL connection and headers
        mock_connect.assert_called_once()
        ws_url = mock_connect.call_args[0][0]
        assert "pNInz6obpgmqMArAY74m/stream-input" in ws_url
        assert "eleven_monolingual_v1" in ws_url
        assert "mp3_44100_128" in ws_url

        extra_headers = mock_connect.call_args[1]["extra_headers"]
        assert extra_headers == [("xi-api-key", "test-key-ws")]

        # Verify initial setup message was sent
        sent_messages = [json.loads(call[0][0]) for call in mock_ws.send.call_args_list]
        assert len(sent_messages) >= 3  # Setup message, token1, token2, end message

        # Verify setup message contents
        assert sent_messages[0]["text"] == " "
        assert "voice_settings" in sent_messages[0]

        # Verify text tokens and end message
        assert sent_messages[1]["text"] == "token1 "
        assert sent_messages[2]["text"] == "token2"
        assert sent_messages[3]["text"] == ""
