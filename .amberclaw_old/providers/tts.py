"""Text-to-Speech providers (AC-076)."""

import os
from pathlib import Path
from typing import Protocol

import httpx
from loguru import logger


class TTSProvider(Protocol):
    """Protocol for TTS providers."""

    async def generate(self, text: str, output_path: str | Path) -> bool:
        """Generate audio from text."""
        ...


class OpenAIttsProvider:
    """TTS provider using OpenAI's TTS API."""

    def __init__(self, api_key: str | None = None, model: str = "tts-1", voice: str = "alloy"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.voice = voice
        self.api_url = "https://api.openai.com/v1/audio/speech"

    async def generate(self, text: str, output_path: str | Path) -> bool:
        """Generate audio from text using OpenAI."""
        if not self.api_key:
            logger.warning("OpenAI API key not configured for TTS")
            return False

        try:
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {self.api_key}"}
                data = {
                    "model": self.model,
                    "input": text,
                    "voice": self.voice,
                }
                response = await client.post(self.api_url, headers=headers, json=data, timeout=60.0)
                response.raise_for_status()

                with open(output_path, "wb") as f:
                    f.write(response.content)
                return True
        except Exception as e:
            logger.error("OpenAI TTS error: {}", e)
            return False


class ElevenLabsTTSProvider:
    """TTS provider using ElevenLabs API."""

    def __init__(self, api_key: str | None = None, voice_id: str = "pNInz6obpgmqMArAY74m"):
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        self.voice_id = voice_id
        self.api_url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

    async def generate(self, text: str, output_path: str | Path) -> bool:
        """Generate audio from text using ElevenLabs."""
        if not self.api_key:
            logger.warning("ElevenLabs API key not configured for TTS")
            return False

        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                    "xi-api-key": self.api_key,
                }
                data = {
                    "text": text,
                    "model_id": "eleven_monolingual_v1",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.5,
                    },
                }
                response = await client.post(self.api_url, headers=headers, json=data, timeout=60.0)
                response.raise_for_status()

                with open(output_path, "wb") as f:
                    f.write(response.content)
                return True
        except Exception as e:
            logger.error("ElevenLabs TTS error: {}", e)
            return False
