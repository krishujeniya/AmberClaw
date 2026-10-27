from typing import Any

from loguru import logger

from amberclaw.voice.neutts import NeuTTS
from amberclaw.voice.stt import SpeechToTextEngine


class DiscordVoiceChannelHandler:
    """Discord voice channel audio streamer and processor."""

    def __init__(
        self,
        stt_engine: SpeechToTextEngine | None = None,
        tts_engine: Any = None,
    ):
        self.stt_engine = stt_engine or SpeechToTextEngine()
        self.tts_engine = tts_engine or NeuTTS()
        self._connected = False

    async def connect_channel(self, channel_id: str) -> bool:
        """Simulate/manage connection to a Discord voice channel."""
        logger.info(f"Connecting to Discord voice channel {channel_id}...")
        self._connected = True
        return True

    async def disconnect_channel(self) -> None:
        """Disconnect from active Discord voice channel."""
        logger.info("Disconnecting from Discord voice channel...")
        self._connected = False

    async def process_user_audio_chunk(
        self, user_id: str, audio_pcm: bytes, agent_callback: Any
    ) -> bytes | None:
        """Process incoming user audio stream chunk from Discord VC, transcribe, and return response audio."""
        if not self._connected or not audio_pcm:
            return None

        text = await self.stt_engine.transcribe_bytes(audio_pcm)
        if not text.strip() or text.startswith("[Simulated"):
            return None

        logger.info(f"Discord VC User {user_id} spoke: {text}")
        agent_reply = await agent_callback(text)

        if hasattr(self.tts_engine, "synthesize"):
            return await self.tts_engine.synthesize(agent_reply)
        return None
