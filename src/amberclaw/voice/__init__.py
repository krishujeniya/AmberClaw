"""
AmberClaw amberclaw.voice module.
"""

from pydantic import BaseModel, Field

from amberclaw.voice.base import (
    AudioConfig,
    AudioSource,
    MicrophoneSource,
    RealTimeStreamer,
    SimulatedAudioSource,
    VoiceActivityDetector,
)
from amberclaw.voice.cli_voice import CLIVoiceLoop
from amberclaw.voice.discord_vc import DiscordVoiceChannelHandler
from amberclaw.voice.elevenlabs import (
    ElevenLabsConfig,
    ElevenLabsTTS,
)
from amberclaw.voice.neutts import NeuTTS, NeuTTSConfig
from amberclaw.voice.realtime import (
    RealtimeSessionManager,
    RealtimeVoiceSession,
    SessionState,
)
from amberclaw.voice.signaling import SignalingMessage, WebRTCSignalingHandler
from amberclaw.voice.stt import SpeechToTextEngine, STTConfig
from amberclaw.voice.telegram_voice import TelegramVoiceHandler


class VoiceModuleConfig(BaseModel):
    """Configuration for the amberclaw.voice module."""

    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = [
    "AudioConfig",
    "AudioSource",
    "CLIVoiceLoop",
    "DiscordVoiceChannelHandler",
    "ElevenLabsConfig",
    "ElevenLabsTTS",
    "MicrophoneSource",
    "NeuTTS",
    "NeuTTSConfig",
    "RealTimeStreamer",
    "RealtimeSessionManager",
    "RealtimeVoiceSession",
    "STTConfig",
    "SessionState",
    "SignalingMessage",
    "SimulatedAudioSource",
    "SpeechToTextEngine",
    "TelegramVoiceHandler",
    "VoiceActivityDetector",
    "VoiceModuleConfig",
    "WebRTCSignalingHandler",
]
