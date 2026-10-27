import asyncio
import base64
import contextlib
import json
import os
from collections.abc import AsyncIterator

import httpx
import websockets
from loguru import logger
from pydantic import BaseModel, Field


class ElevenLabsConfig(BaseModel):
    """Configuration for ElevenLabs Text-to-Speech API."""

    api_key: str | None = Field(
        default=None,
        description="ElevenLabs API Key. Defaults to ELEVENLABS_API_KEY environment variable.",
    )
    voice_id: str = Field(
        default="pNInz6obpgmqMArAY74m",
        description="Voice ID to use for speech generation.",
    )
    model_id: str = Field(
        default="eleven_monolingual_v1", description="Model ID to use for synthesis."
    )
    output_format: str = Field(
        default="mp3_44100_128",
        description="Output audio format (e.g. mp3_44100_128, pcm_16000).",
    )


class ElevenLabsTTS:
    """ElevenLabs streaming Text-to-Speech client."""

    def __init__(self, config: ElevenLabsConfig | None = None):
        self.config = config or ElevenLabsConfig()
        self._api_key = self.config.api_key or os.environ.get("ELEVENLABS_API_KEY")

    def _get_headers(self) -> dict[str, str]:
        if not self._api_key:
            raise ValueError("ElevenLabs API Key is not configured.")
        return {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

    async def stream_tts_http(self, text: str) -> AsyncIterator[bytes]:
        """Stream audio for a fixed text input via ElevenLabs HTTP streaming API."""
        if not self._api_key:
            raise ValueError("ElevenLabs API Key is not configured.")

        url = (
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.config.voice_id}/stream"
        )
        params = {"output_format": self.config.output_format}
        data = {
            "text": text,
            "model_id": self.config.model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.8,
            },
        }

        async with (
            httpx.AsyncClient() as client,
            client.stream(
                "POST",
                url,
                params=params,
                headers=self._get_headers(),
                json=data,
                timeout=60.0,
            ) as response,
        ):
            if response.status_code != 200:  # noqa: PLR2004
                error_text = await response.aread()
                logger.error(
                    "ElevenLabs HTTP request failed with code {}: {}",
                    response.status_code,
                    error_text,
                )
                response.raise_for_status()

            async for chunk in response.aiter_bytes():
                yield chunk

    async def stream_tts_websocket(
        self, text_iterator: AsyncIterator[str]
    ) -> AsyncIterator[bytes]:
        """Stream audio chunks via bidirectional WebSocket connection, feeding text tokens dynamically."""
        if not self._api_key:
            raise ValueError("ElevenLabs API Key is not configured.")

        ws_url = (
            f"wss://api.elevenlabs.io/v1/text-to-speech/{self.config.voice_id}/stream-input"
            f"?model_id={self.config.model_id}&output_format={self.config.output_format}"
        )

        headers = [("xi-api-key", self._api_key)]

        async with websockets.connect(ws_url, extra_headers=headers) as websocket:
            setup_msg = {
                "text": " ",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.8,
                },
                "generation_config": {"chunk_length_schedule": [120, 160, 200, 240]},
            }
            await websocket.send(json.dumps(setup_msg))

            async def sender() -> None:
                try:
                    async for text_chunk in text_iterator:
                        if not text_chunk:
                            continue
                        msg = {"text": text_chunk, "try_trigger_generation": True}
                        await websocket.send(json.dumps(msg))

                    end_msg = {"text": ""}
                    await websocket.send(json.dumps(end_msg))
                except Exception as ex:
                    logger.error("Error sending text to ElevenLabs WS: {}", ex)
                    with contextlib.suppress(Exception):
                        await websocket.send(json.dumps({"text": ""}))

            sender_task = asyncio.create_task(sender())

            try:
                async for message in websocket:
                    msg_str = (
                        message.decode("utf-8")
                        if isinstance(message, bytes)
                        else message
                    )
                    data = json.loads(msg_str)
                    if data.get("audio"):
                        audio_chunk = base64.b64decode(data["audio"])
                        yield audio_chunk

                    if data.get("isFinal"):
                        break
            finally:
                if not sender_task.done():
                    sender_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await sender_task
