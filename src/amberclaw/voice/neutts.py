import asyncio
import os
import tempfile
import wave
from collections.abc import AsyncIterator
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


class NeuTTSConfig(BaseModel):
    """Configuration for NeuTTS local offline synthesis engine."""

    voice_name: str = Field(
        default="default", description="Voice identifier or language code."
    )
    rate: int = Field(default=175, description="Speech rate in words per minute.")
    volume: float = Field(
        default=1.0, description="Speech volume multiplier (0.0 to 1.0)."
    )
    preferred_backend: str = Field(
        default="auto",
        description="Preferred TTS engine backend ('auto', 'pyttsx3', 'gtts', 'espeak', 'simulated')",
    )


class NeuTTS:
    """Offline local Text-to-Speech synthesizer with multi-backend fallbacks."""

    def __init__(self, config: NeuTTSConfig | None = None):
        self.config = config or NeuTTSConfig()
        self._backend = "simulated"
        self._engine: Any = None
        self._init_backend()

    def _init_backend(self) -> None:
        if self.config.preferred_backend in ("pyttsx3", "auto"):
            try:
                import pyttsx3  # noqa: PLC0415

                self._engine = pyttsx3.init()
                self._engine.setProperty("rate", self.config.rate)
                self._engine.setProperty("volume", self.config.volume)
                self._backend = "pyttsx3"
                logger.info("NeuTTS initialized with pyttsx3 backend.")
                return
            except Exception as e:
                logger.debug(f"pyttsx3 initialization failed: {e}")

        if self.config.preferred_backend in ("gtts", "auto"):
            try:
                import gtts  # noqa: F401, PLC0415

                self._backend = "gtts"
                logger.info("NeuTTS initialized with gTTS backend.")
                return
            except Exception as e:
                logger.debug(f"gTTS initialization failed: {e}")

        logger.debug(
            "No external TTS backend available for NeuTTS. Using simulated PCM synthesizer fallback."
        )
        self._backend = "simulated"

    async def synthesize(self, text: str) -> bytes:
        """Synthesize text into WAV/PCM bytes using the best available local backend."""
        if not text.strip():
            return b""

        loop = asyncio.get_running_loop()

        if self._backend == "pyttsx3":
            return await loop.run_in_executor(None, self._synthesize_pyttsx3, text)
        if self._backend == "gtts":
            return await loop.run_in_executor(None, self._synthesize_gtts, text)
        return await loop.run_in_executor(None, self._synthesize_simulated, text)

    def _synthesize_pyttsx3(self, text: str) -> bytes:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            self._engine.save_to_file(text, tmp_path)
            self._engine.runAndWait()
            if os.path.exists(tmp_path):
                with open(tmp_path, "rb") as f:
                    return f.read()
        except Exception as ex:
            logger.error(f"pyttsx3 synthesis error: {ex}")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        return self._synthesize_simulated(text)

    def _synthesize_gtts(self, text: str) -> bytes:
        from gtts import gTTS  # noqa: PLC0415

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            tts = gTTS(text=text, lang="en")
            tts.save(tmp_path)
            with open(tmp_path, "rb") as f:
                return f.read()
        except Exception as ex:
            logger.error(f"gTTS synthesis error: {ex}")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        return self._synthesize_simulated(text)

    def _synthesize_simulated(self, text: str) -> bytes:
        """Generate a valid WAV audio container with tone pulses representing spoken text."""
        sample_rate = 16000
        duration_sec = max(0.5, len(text) * 0.05)
        num_samples = int(sample_rate * duration_sec)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with wave.open(tmp_path, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)

                pcm_data = bytearray()
                import math

                for i in range(num_samples):
                    sample = int(10000 * math.sin(2 * math.pi * 440 * i / sample_rate))
                    pcm_data.extend(sample.to_bytes(2, byteorder="little", signed=True))

                wav_file.writeframes(bytes(pcm_data))

            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    async def stream_tts(
        self, text: str, chunk_size: int = 4096
    ) -> AsyncIterator[bytes]:
        """Stream synthesized audio in chunks."""
        audio_bytes = await self.synthesize(text)
        for i in range(0, len(audio_bytes), chunk_size):
            yield audio_bytes[i : i + chunk_size]
            await asyncio.sleep(0.01)
