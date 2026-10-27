# ruff: noqa: PLR2004
import asyncio
import math
import struct

import pytest

from amberclaw.voice.base import (
    AudioConfig,
    MicrophoneSource,
    RealTimeStreamer,
    SimulatedAudioSource,
    VoiceActivityDetector,
)


def test_audio_config() -> None:
    config = AudioConfig()
    assert config.sample_rate == 16000
    assert config.channels == 1
    assert config.chunk_size == 512
    assert config.bytes_per_sample == 2


@pytest.mark.asyncio
async def test_simulated_audio_source() -> None:
    config = AudioConfig(chunk_size=256)
    source = SimulatedAudioSource(
        config, frequency=440.0, volume=0.5, simulate_speech=False
    )

    await source.start()
    chunks = []
    async for chunk in source.chunks():
        chunks.append(chunk)
        if len(chunks) == 3:
            break
    await source.stop()

    assert len(chunks) == 3
    # Check chunk byte size: 256 frames * 2 bytes/sample * 1 channel = 512 bytes
    for chunk in chunks:
        assert len(chunk) == 512

        # Verify it has sine wave energy (non-zero)
        count = len(chunk) // 2
        samples = struct.unpack(f"<{count}h", chunk)
        has_non_zero = any(s != 0 for s in samples)
        assert has_non_zero is True


@pytest.mark.asyncio
async def test_microphone_source_fallback() -> None:
    config = AudioConfig(chunk_size=128)
    # MicrophoneSource should fallback to simulated if pyaudio/sounddevice are not installed
    source = MicrophoneSource(config)

    await source.start()
    chunks = []
    async for chunk in source.chunks():
        chunks.append(chunk)
        if len(chunks) == 2:
            break
    await source.stop()

    assert len(chunks) == 2
    for chunk in chunks:
        assert len(chunk) == 256


def test_voice_activity_detector() -> None:
    config = AudioConfig()
    vad = VoiceActivityDetector(config, energy_threshold=100.0, silence_timeout_sec=0.2)

    # 1. Test RMS calculation for silence
    silence_chunk = b"\x00" * (config.chunk_size * 2)
    assert vad.calculate_rms(silence_chunk) == 0.0
    assert vad.is_speech(silence_chunk) is False

    # 2. Test RMS calculation for loud sine wave segment
    loud_samples = []
    for i in range(config.chunk_size):
        # Sine wave with amplitude 10000
        val = int(math.sin(i * 0.1) * 10000)
        loud_samples.append(val)
    loud_chunk = struct.pack(f"<{config.chunk_size}h", *loud_samples)

    rms = vad.calculate_rms(loud_chunk)
    assert rms > 5000.0
    assert vad.is_speech(loud_chunk) is True


@pytest.mark.asyncio
async def test_realtime_streamer_segmentation() -> None:
    config = AudioConfig(chunk_size=128, sample_rate=8000)
    # Use SimulatedAudioSource with speech simulation
    source = SimulatedAudioSource(
        config, frequency=440.0, volume=0.8, simulate_speech=True
    )
    vad = VoiceActivityDetector(config, energy_threshold=500.0, silence_timeout_sec=0.1)
    streamer = RealTimeStreamer(source, vad)

    # We will run streamer in a task, and let it stream briefly
    utterances = []

    async def collect() -> None:
        async for utt in streamer.stream_utterances():
            utterances.append(utt)
            if len(utterances) == 1:
                break

    task = asyncio.create_task(collect())

    # Wait up to 3 seconds for collection, or cancel
    try:
        await asyncio.wait_for(task, timeout=3.0)
    except TimeoutError:
        task.cancel()

    # Since we simulate speech intervals, we should have captured at least 1 segmented speech block
    assert len(utterances) >= 1
    assert len(utterances[0]) > 0


@pytest.mark.asyncio
async def test_realtime_streamer_interruption() -> None:
    config = AudioConfig(chunk_size=128, sample_rate=8000)
    source = SimulatedAudioSource(
        config, frequency=440.0, volume=0.8, simulate_speech=False
    )
    vad = VoiceActivityDetector(config, energy_threshold=100.0, silence_timeout_sec=0.5)
    streamer = RealTimeStreamer(source, vad)

    # Start streamer, then immediately interrupt it
    async def run_stream() -> None:
        async for _ in streamer.stream_utterances():
            pass

    task = asyncio.create_task(run_stream())
    await asyncio.sleep(0.1)

    streamer.interrupt()
    await task  # Should exit quickly
    assert streamer._interrupted is True
