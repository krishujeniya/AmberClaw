import pytest

from amberclaw.voice.base import (
    AudioConfig,
    SimulatedAudioSource,
)
from amberclaw.voice.discord_vc import DiscordVoiceChannelHandler
from amberclaw.voice.neutts import NeuTTS, NeuTTSConfig
from amberclaw.voice.stt import SpeechToTextEngine, STTConfig
from amberclaw.voice.telegram_voice import TelegramVoiceHandler


@pytest.mark.asyncio
async def test_simulated_audio_source():
    config = AudioConfig(sample_rate=16000, chunk_size=320)
    source = SimulatedAudioSource(config, frequency=440.0)
    await source.start()

    chunks = []
    async for chunk in source.chunks():
        chunks.append(chunk)
        if len(chunks) >= 3:
            break

    await source.stop()
    assert len(chunks) == 3
    assert len(chunks[0]) == 320 * 2  # 16-bit PCM (2 bytes per sample)


@pytest.mark.asyncio
async def test_neutts_synthesis():
    config = NeuTTSConfig(preferred_backend="simulated")
    tts = NeuTTS(config)
    audio_bytes = await tts.synthesize("Hello world! This is a test.")
    assert len(audio_bytes) > 0
    assert audio_bytes.startswith(b"RIFF")


@pytest.mark.asyncio
async def test_stt_engine_transcription():
    config = STTConfig(provider="simulated")
    stt = SpeechToTextEngine(config)
    pcm_data = b"\x00" * 3200
    text = await stt.transcribe_bytes(pcm_data)
    assert len(text) > 0


@pytest.mark.asyncio
async def test_telegram_voice_handler():
    stt = SpeechToTextEngine(STTConfig(provider="simulated"))
    tts = NeuTTS(NeuTTSConfig(preferred_backend="simulated"))
    handler = TelegramVoiceHandler(stt_engine=stt, tts_engine=tts)

    async def mock_agent(text: str) -> str:
        return f"Echoing: {text}"

    text_resp, audio_resp = await handler.handle_voice_message(
        b"\x00" * 3200, mock_agent
    )
    assert "Echoing:" in text_resp
    assert audio_resp is not None
    assert audio_resp.startswith(b"RIFF")


@pytest.mark.asyncio
async def test_discord_vc_handler():
    stt = SpeechToTextEngine(STTConfig(provider="simulated"))
    tts = NeuTTS(NeuTTSConfig(preferred_backend="simulated"))
    handler = DiscordVoiceChannelHandler(stt_engine=stt, tts_engine=tts)

    connected = await handler.connect_channel("123456789")
    assert connected is True

    await handler.disconnect_channel()
    assert handler._connected is False
