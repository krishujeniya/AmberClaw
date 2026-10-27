import asyncio
from typing import Any

from loguru import logger

from amberclaw.voice.base import (
    AudioConfig,
    MicrophoneSource,
    RealTimeStreamer,
    VoiceActivityDetector,
)
from amberclaw.voice.elevenlabs import ElevenLabsTTS
from amberclaw.voice.neutts import NeuTTS
from amberclaw.voice.stt import SpeechToTextEngine


class CLIVoiceLoop:
    """Interactive CLI terminal voice conversation handler."""

    def __init__(
        self,
        stt_engine: SpeechToTextEngine | None = None,
        tts_engine: Any = None,
        config: AudioConfig | None = None,
    ):
        self.config = config or AudioConfig()
        self.stt_engine = stt_engine or SpeechToTextEngine()
        self.tts_engine = tts_engine or NeuTTS()
        self.source = MicrophoneSource(self.config)
        self.vad = VoiceActivityDetector(self.config)
        self.streamer = RealTimeStreamer(self.source, self.vad)
        self._running = False

    async def start(self, agent_callback: Any = None) -> None:
        """Start listening for speech input, transcribing, and synthesizing responses."""
        self._running = True
        logger.info("CLI Voice loop active. Speak into microphone (Ctrl+C to stop)...")

        try:
            async for utterance_bytes in self.streamer.stream_utterances():
                if not self._running:
                    break

                text = await self.stt_engine.transcribe_bytes(utterance_bytes)
                if not text.strip():
                    continue

                logger.info(f"User Spoke: {text}")

                # Pass transcribed text to agent handler if provided
                response_text = f"Received voice input: '{text}'"
                if agent_callback:
                    try:
                        response_text = await agent_callback(text)
                    except Exception as ex:
                        logger.error(f"Error processing agent callback: {ex}")
                        response_text = (
                            "I encountered an error processing your command."
                        )

                logger.info(f"Agent Response: {response_text}")

                # Synthesize agent response to speech audio
                if isinstance(self.tts_engine, ElevenLabsTTS):
                    async for chunk in self.tts_engine.stream_tts_http(response_text):
                        pass
                elif hasattr(self.tts_engine, "synthesize"):
                    await self.tts_engine.synthesize(response_text)

        except asyncio.CancelledError:
            logger.info("CLI Voice loop stopped.")
        finally:
            self._running = False

    def stop(self) -> None:
        self._running = False
        self.streamer.interrupt()
