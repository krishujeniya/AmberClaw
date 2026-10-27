import abc
import asyncio
import math
import struct
import time
from collections.abc import AsyncIterator
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


class AudioConfig(BaseModel):
    """Configuration for audio capture and playback."""

    sample_rate: int = Field(default=16000, description="Audio sample rate in Hz")
    channels: int = Field(default=1, description="Number of audio channels")
    chunk_size: int = Field(default=512, description="Audio chunk size in frames")
    bytes_per_sample: int = Field(
        default=2, description="Bytes per sample (e.g., 2 bytes for 16-bit PCM)"
    )


class AudioSource(abc.ABC):
    """Abstract base class for audio input streams."""

    @abc.abstractmethod
    async def start(self) -> None:
        """Start capturing audio."""
        pass

    @abc.abstractmethod
    async def stop(self) -> None:
        """Stop capturing audio."""
        pass

    @abc.abstractmethod
    def chunks(self) -> AsyncIterator[bytes]:
        """Asynchronously yield raw PCM audio chunks."""
        pass


class SimulatedAudioSource(AudioSource):
    """A simulated audio source that generates sine wave tones or silence."""

    def __init__(
        self,
        config: AudioConfig,
        frequency: float = 440.0,
        volume: float = 0.5,
        simulate_speech: bool = False,
    ):
        self.config = config
        self.frequency = frequency
        self.volume = volume
        self.simulate_speech = simulate_speech
        self._running = False
        self._phase = 0.0

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def chunks(self) -> AsyncIterator[bytes]:
        chunk_duration = self.config.chunk_size / self.config.sample_rate
        chunk_count = 0
        while self._running:
            start_time = time.perf_counter()

            # Determine dynamic amplitude if simulating speech intervals
            # e.g., speak for 10 chunks, silent for 15 chunks
            amplitude = self.volume
            if self.simulate_speech and (chunk_count // 10) % 2 == 1:
                amplitude = 0.0  # Silence
            chunk_count += 1

            # Generate PCM 16-bit sine wave chunk
            chunk_data = bytearray()
            for _ in range(self.config.chunk_size):
                if amplitude > 0.0:
                    val = math.sin(self._phase) * amplitude * 32767.0
                    sample = int(max(-32768, min(32767, val)))
                    # Update phase
                    self._phase += (
                        2.0 * math.pi * self.frequency / self.config.sample_rate
                    )
                    if self._phase > 2.0 * math.pi:
                        self._phase -= 2.0 * math.pi
                else:
                    sample = 0

                chunk_data.extend(struct.pack("<h", sample))

            yield bytes(chunk_data)

            # Control rate
            elapsed = time.perf_counter() - start_time
            sleep_time = max(0.0, chunk_duration - elapsed)
            await asyncio.sleep(sleep_time)


class MicrophoneSource(AudioSource):
    """Microphone audio source that dynamically binds to PyAudio or Sounddevice."""

    def __init__(self, config: AudioConfig):
        self.config = config
        self._running = False
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._backend = ""
        self._stream: Any = None
        self._pa: Any = None
        self._simulated: SimulatedAudioSource | None = None

    def _init_backend(self) -> None:
        # Try PyAudio first
        try:
            import pyaudio  # noqa: PLC0415

            self._backend = "pyaudio"
            self._pa = pyaudio.PyAudio()
            return
        except ImportError:
            pass

        # Try Sounddevice next
        try:
            import sounddevice  # noqa: F401, PLC0415

            self._backend = "sounddevice"
            return
        except ImportError:
            pass

        # Fallback to simulated stream
        logger.warning(
            "Microphone hardware backend not found. Falling back to SimulatedAudioSource."
        )
        self._backend = "simulated"
        self._simulated = SimulatedAudioSource(self.config)

    async def start(self) -> None:
        if self._running:
            return

        self._init_backend()
        self._running = True

        if self._backend == "simulated" and self._simulated:
            await self._simulated.start()
        elif self._backend == "pyaudio":
            import pyaudio  # noqa: PLC0415

            # Run blocking pyaudio stream creation in executor
            loop = asyncio.get_running_loop()

            def _open_stream() -> Any:
                return self._pa.open(
                    format=pyaudio.paInt16,
                    channels=self.config.channels,
                    rate=self.config.sample_rate,
                    input=True,
                    frames_per_buffer=self.config.chunk_size,
                    stream_callback=self._pyaudio_callback,
                )

            self._stream = await loop.run_in_executor(None, _open_stream)
        elif self._backend == "sounddevice":
            import sounddevice as sd  # noqa: PLC0415

            loop = asyncio.get_running_loop()

            def _pyaudio_sd_callback(
                indata: Any, _frames: Any, _time_info: Any, _status: Any
            ) -> None:
                loop.call_soon_threadsafe(self._queue.put_nowait, indata.tobytes())

            def _open_sd_stream() -> Any:
                return sd.RawInputStream(
                    samplerate=self.config.sample_rate,
                    blocksize=self.config.chunk_size,
                    channels=self.config.channels,
                    dtype="int16",
                    callback=_pyaudio_sd_callback,
                )

            self._stream = await loop.run_in_executor(None, _open_sd_stream)
            self._stream.start()

    def _pyaudio_callback(
        self, in_data: Any, _frame_count: Any, _time_info: Any, _status: Any
    ) -> Any:
        loop = asyncio.get_event_loop()
        loop.call_soon_threadsafe(self._queue.put_nowait, in_data)
        import pyaudio  # noqa: PLC0415

        return (None, pyaudio.paContinue)

    async def stop(self) -> None:
        if not self._running:
            return

        self._running = False
        if self._backend == "simulated" and self._simulated:
            await self._simulated.stop()
        elif self._backend == "pyaudio" and self._stream:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._stream.stop_stream)
            await loop.run_in_executor(None, self._stream.close)
            self._pa.terminate()
        elif self._backend == "sounddevice" and self._stream:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._stream.stop)
            await loop.run_in_executor(None, self._stream.close)

        self._stream = None

    async def chunks(self) -> AsyncIterator[bytes]:
        if self._backend == "simulated" and self._simulated:
            async for chunk in self._simulated.chunks():
                yield chunk
        else:
            while self._running:
                try:
                    # Fetch from queue
                    chunk = await self._queue.get()
                    yield chunk
                except asyncio.CancelledError:
                    break


class VoiceActivityDetector:
    """Stateful energy-based voice activity detector."""

    def __init__(
        self,
        config: AudioConfig,
        energy_threshold: float = 300.0,
        silence_timeout_sec: float = 1.0,
    ):
        self.config = config
        self.energy_threshold = energy_threshold
        self.silence_timeout_sec = silence_timeout_sec
        self._is_speaking = False
        self._last_speech_time = 0.0

    def calculate_rms(self, chunk: bytes) -> float:
        """Calculate Root Mean Square (RMS) energy of PCM 16-bit audio chunk."""
        count = len(chunk) // self.config.bytes_per_sample
        if count == 0:
            return 0.0

        # Unpack as little-endian short integers
        fmt = f"<{count}h"
        try:
            samples = struct.unpack(fmt, chunk)
        except Exception:
            return 0.0

        sum_squares = sum(float(sample) * sample for sample in samples)
        return math.sqrt(sum_squares / count)

    def is_speech(self, chunk: bytes) -> bool:
        """Assess if the chunk represents speech based on RMS energy."""
        rms = self.calculate_rms(chunk)
        now = time.time()

        if rms > self.energy_threshold:
            if not self._is_speaking:
                self._is_speaking = True
            self._last_speech_time = now
            return True

        if self._is_speaking:
            if now - self._last_speech_time > self.silence_timeout_sec:
                self._is_speaking = False
                return False
            return True

        return False


class RealTimeStreamer:
    """Orchestrates an AudioSource and VAD to stream segmented speech utterances."""

    def __init__(self, source: AudioSource, vad: VoiceActivityDetector):
        self.source = source
        self.vad = vad
        self._interrupted = False

    def interrupt(self) -> None:
        """Thread-safe trigger to abort current streaming/processing."""
        self._interrupted = True

    async def stream_utterances(self) -> AsyncIterator[bytes]:
        """Yield entire speech utterances as single concatenated byte blocks."""
        self._interrupted = False
        await self.source.start()

        utterance = bytearray()
        try:
            async for chunk in self.source.chunks():
                if self._interrupted:
                    break

                if self.vad.is_speech(chunk):
                    utterance.extend(chunk)
                elif len(utterance) > 0:
                    yield bytes(utterance)
                    utterance = bytearray()
        finally:
            await self.source.stop()
