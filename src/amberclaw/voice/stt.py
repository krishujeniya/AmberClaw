import asyncio
import io
import os
import tempfile
import wave
from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel, Field


class STTConfig(BaseModel):
    """Configuration for Speech-To-Text Recognition engine."""

    provider: str = Field(
        default="auto",
        description="STT provider backend ('auto', 'whisper_api', 'local_whisper', 'google', 'simulated')",
    )
    api_key: str | None = Field(
        default=None,
        description="API Key for cloud STT services (e.g. OpenAI API key).",
    )
    model: str = Field(
        default="whisper-1", description="Model name for Whisper transcription."
    )
    language: str = Field(
        default="en", description="Language code for speech recognition."
    )


class SpeechToTextEngine:
    """Multi-provider Speech-To-Text transcription engine."""

    def __init__(self, config: STTConfig | None = None):
        self.config = config or STTConfig()
        self._api_key = self.config.api_key or os.environ.get("OPENAI_API_KEY")
        self._backend = "simulated"
        self._local_model: Any = None
        self._init_backend()

    def _init_backend(self) -> None:
        provider = self.config.provider

        if provider in ("whisper_api", "auto") and self._api_key:
            self._backend = "whisper_api"
            logger.info("SpeechToTextEngine initialized with OpenAI Whisper API.")
            return

        if provider in ("local_whisper", "auto"):
            try:
                import faster_whisper  # noqa: PLC0415

                self._local_model = faster_whisper.WhisperModel(
                    "base", device="cpu", compute_type="int8"
                )
                self._backend = "local_whisper"
                logger.info("SpeechToTextEngine initialized with local faster_whisper.")
                return
            except Exception:
                try:
                    import whisper  # noqa: PLC0415

                    self._local_model = whisper.load_model("base")
                    self._backend = "local_whisper"
                    logger.info("SpeechToTextEngine initialized with local whisper.")
                    return
                except Exception as e:
                    logger.debug(f"Local whisper initialization failed: {e}")

        if provider in ("google", "auto"):
            try:
                import speech_recognition as sr  # noqa: F401, PLC0415

                self._backend = "google"
                logger.info(
                    "SpeechToTextEngine initialized with Google Speech Recognition."
                )
                return
            except Exception as e:
                logger.debug(f"Google speech_recognition initialization failed: {e}")

        logger.debug(
            "No external STT engine available. Using simulated transcription backend."
        )
        self._backend = "simulated"

    async def transcribe_bytes(
        self, audio_data: bytes, sample_rate: int = 16000
    ) -> str:
        """Transcribe raw PCM/WAV audio bytes into text."""
        if not audio_data:
            return ""

        # Wrap raw PCM into standard WAV format if header missing
        wav_bytes = audio_data
        if not audio_data.startswith(b"RIFF"):
            wav_bytes = self._pcm_to_wav(audio_data, sample_rate=sample_rate)

        loop = asyncio.get_running_loop()

        if self._backend == "whisper_api":
            return await self._transcribe_whisper_api(wav_bytes)
        if self._backend == "local_whisper":
            return await loop.run_in_executor(
                None, self._transcribe_local_whisper, wav_bytes
            )
        if self._backend == "google":
            return await loop.run_in_executor(None, self._transcribe_google, wav_bytes)
        return await loop.run_in_executor(None, self._transcribe_simulated, wav_bytes)

    async def _transcribe_whisper_api(self, wav_bytes: bytes) -> str:
        url = "https://api.openai.com/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {self._api_key}"}

        files = {"file": ("speech.wav", io.BytesIO(wav_bytes), "audio/wav")}
        data = {"model": self.config.model, "language": self.config.language}

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url, headers=headers, files=files, data=data, timeout=30.0
                )
                if resp.status_code == 200:  # noqa: PLR2004
                    result = resp.json()
                    return result.get("text", "").strip()
                logger.error(f"Whisper API error ({resp.status_code}): {resp.text}")
        except Exception as ex:
            logger.error(f"Whisper API exception: {ex}")

        return self._transcribe_simulated(wav_bytes)

    def _transcribe_local_whisper(self, wav_bytes: bytes) -> str:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name

        try:
            if hasattr(self._local_model, "transcribe"):
                # faster_whisper or whisper model
                segments, _ = self._local_model.transcribe(tmp_path)
                if isinstance(segments, list):
                    return " ".join([s.text for s in segments]).strip()
                return " ".join([segment.text for segment in segments]).strip()
        except Exception as ex:
            logger.error(f"Local Whisper transcription error: {ex}")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        return self._transcribe_simulated(wav_bytes)

    def _transcribe_google(self, wav_bytes: bytes) -> str:
        import speech_recognition as sr  # noqa: PLC0415

        recognizer = sr.Recognizer()
        with io.BytesIO(wav_bytes) as audio_file:
            try:
                with sr.AudioFile(audio_file) as source:
                    audio = recognizer.record(source)
                    return recognizer.recognize_google(
                        audio, language=self.config.language
                    )
            except Exception as ex:
                logger.error(f"Google STT error: {ex}")

        return self._transcribe_simulated(wav_bytes)

    def _transcribe_simulated(self, wav_bytes: bytes) -> str:
        """Fallback transcription return string."""
        if len(wav_bytes) < 100:
            return ""
        return "[Simulated Audio Speech Transcription]"

    def _pcm_to_wav(
        self, pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1
    ) -> bytes:
        with io.BytesIO() as wav_io:
            with wave.open(wav_io, "wb") as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(pcm_bytes)
            return wav_io.getvalue()
