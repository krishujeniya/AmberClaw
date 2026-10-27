from typing import Any

from loguru import logger

from amberclaw.voice.neutts import NeuTTS
from amberclaw.voice.stt import SpeechToTextEngine


class TelegramVoiceHandler:
    """Telegram voice message adapter for transcribing incoming audio notes and synthesizing voice responses."""

    def __init__(
        self,
        stt_engine: SpeechToTextEngine | None = None,
        tts_engine: Any = None,
    ):
        self.stt_engine = stt_engine or SpeechToTextEngine()
        self.tts_engine = tts_engine or NeuTTS()

    async def handle_voice_message(
        self,
        audio_bytes: bytes,
        agent_callback: Any,
    ) -> tuple[str, bytes | None]:
        """Process incoming voice note audio bytes, transcribe speech, route to agent, and return text + audio reply."""
        if not audio_bytes:
            return "No audio data received.", None

        # Convert/transcribe speech to text
        transcribed_text = await self.stt_engine.transcribe_bytes(audio_bytes)
        logger.info(f"Telegram voice note transcribed: '{transcribed_text}'")

        if not transcribed_text.strip():
            return "Could not recognize speech in voice message.", None

        # Execute agent workflow
        agent_response_text = await agent_callback(transcribed_text)

        # Synthesize reply audio
        reply_audio_bytes: bytes | None = None
        try:
            if hasattr(self.tts_engine, "synthesize"):
                reply_audio_bytes = await self.tts_engine.synthesize(
                    agent_response_text
                )
        except Exception as ex:
            logger.error(f"Error synthesizing voice response for Telegram: {ex}")

        return agent_response_text, reply_audio_bytes
