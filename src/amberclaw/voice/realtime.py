import asyncio
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

from loguru import logger
from pydantic import BaseModel

from amberclaw.voice.base import AudioConfig, VoiceActivityDetector
from amberclaw.voice.neutts import NeuTTS
from amberclaw.voice.stt import SpeechToTextEngine


class SessionState(BaseModel):
    """Current state of a real-time voice session."""

    session_id: str
    is_active: bool = True
    is_speaking: bool = False
    is_agent_speaking: bool = False
    interrupted_count: int = 0


class RealtimeVoiceSession:
    """Full-duplex real-time WebRTC/audio voice session with barge-in interruption handling."""

    def __init__(
        self,
        session_id: str | None = None,
        stt_engine: SpeechToTextEngine | None = None,
        tts_engine: Any = None,
        audio_config: AudioConfig | None = None,
        agent_callback: Callable[[str], Any] | None = None,
    ):
        self.session_id = session_id or str(uuid.uuid4())
        self.config = audio_config or AudioConfig()
        self.stt_engine = stt_engine or SpeechToTextEngine()
        self.tts_engine = tts_engine or NeuTTS()
        self.agent_callback = agent_callback
        self.vad = VoiceActivityDetector(self.config)

        self.state = SessionState(session_id=self.session_id)
        self._input_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._output_queue: asyncio.Queue[bytes] = asyncio.Queue()

        self._processing_task: asyncio.Task | None = None
        self._tts_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start background processing tasks for full-duplex audio stream handling."""
        async with self._lock:
            self.state.is_active = True
            if self._processing_task is None or self._processing_task.done():
                self._processing_task = asyncio.create_task(self._process_input_loop())
            logger.info(f"RealtimeVoiceSession {self.session_id} started.")

    async def stop(self) -> None:
        """Terminate the voice session and cancel active audio streams."""
        async with self._lock:
            self.state.is_active = False
            self.cancel_outbound_tts()

            if self._processing_task and not self._processing_task.done():
                self._processing_task.cancel()
                try:
                    await self._processing_task
                except asyncio.CancelledError:
                    pass
            logger.info(f"RealtimeVoiceSession {self.session_id} stopped.")

    def push_audio_chunk(self, chunk: bytes) -> None:
        """Push inbound audio frame (PCM bytes) from client/WebRTC track into input queue."""
        if not self.state.is_active or not chunk:
            return

        # Check for barge-in user speech while agent is speaking
        if self.state.is_agent_speaking and self.vad.is_speech(chunk):
            logger.info(
                f"Barge-in detected on session {self.session_id}! Interrupting agent playback."
            )
            self.cancel_outbound_tts()
            self.state.interrupted_count += 1

        self._input_queue.put_nowait(chunk)

    def cancel_outbound_tts(self) -> None:
        """Barge-in interruption handler: immediately aborts current outbound TTS playback."""
        if self._tts_task and not self._tts_task.done():
            self._tts_task.cancel()
        self.state.is_agent_speaking = False

        # Drain pending output queue
        while not self._output_queue.empty():
            try:
                self._output_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def _process_input_loop(self) -> None:
        """Process inbound PCM chunks, segment speech using VAD, transcribe, and route to agent."""
        utterance_buffer = bytearray()

        while self.state.is_active:
            try:
                chunk = await asyncio.wait_for(self._input_queue.get(), timeout=0.1)
                is_speech = self.vad.is_speech(chunk)

                if is_speech:
                    self.state.is_speaking = True
                    utterance_buffer.extend(chunk)
                elif self.state.is_speaking and len(utterance_buffer) > 0:
                    self.state.is_speaking = False
                    speech_pcm = bytes(utterance_buffer)
                    utterance_buffer.clear()

                    # Transcribe and synthesize response asynchronously
                    await self._handle_completed_utterance(speech_pcm)

            except TimeoutError:
                if self.state.is_speaking and len(utterance_buffer) > 0:
                    self.state.is_speaking = False
                    speech_pcm = bytes(utterance_buffer)
                    utterance_buffer.clear()
                    await self._handle_completed_utterance(speech_pcm)
            except asyncio.CancelledError:
                break
            except Exception as ex:
                logger.error(f"Error in realtime voice input loop: {ex}")

    async def _handle_completed_utterance(self, pcm_bytes: bytes) -> None:
        """Transcribe speech utterance, invoke agent callback, and trigger TTS streaming."""
        text = await self.stt_engine.transcribe_bytes(pcm_bytes)
        if not text.strip() or text.startswith("[Simulated"):
            return

        logger.info(f"Realtime Session {self.session_id} transcribed speech: '{text}'")

        response_text = f"Received: '{text}'"
        if self.agent_callback:
            try:
                response_text = await self.agent_callback(text)
            except Exception as ex:
                logger.error(f"Agent callback error: {ex}")
                response_text = "I ran into an error processing your query."

        # Trigger TTS streaming output in dedicated task
        self.cancel_outbound_tts()
        self._tts_task = asyncio.create_task(self._stream_response_tts(response_text))

    async def _stream_response_tts(self, text: str) -> None:
        """Synthesize response text to audio bytes and push into output queue for WebRTC streaming."""
        self.state.is_agent_speaking = True
        try:
            if hasattr(self.tts_engine, "synthesize"):
                audio_bytes = await self.tts_engine.synthesize(text)
                if audio_bytes and self.state.is_agent_speaking:
                    await self._output_queue.put(audio_bytes)
        except asyncio.CancelledError:
            logger.debug(f"TTS output cancelled for session {self.session_id}")
        except Exception as ex:
            logger.error(f"TTS synthesis error in realtime session: {ex}")
        finally:
            self.state.is_agent_speaking = False

    async def get_outbound_audio(self) -> AsyncIterator[bytes]:
        """Yield outbound audio PCM chunks to send over WebRTC/WebSocket client track."""
        while self.state.is_active:
            try:
                chunk = await asyncio.wait_for(self._output_queue.get(), timeout=0.2)
                yield chunk
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break


class RealtimeSessionManager:
    """Orchestrates active RealtimeVoiceSession instances."""

    def __init__(self):
        self.sessions: dict[str, RealtimeVoiceSession] = {}

    def create_session(
        self,
        session_id: str | None = None,
        agent_callback: Callable[[str], Any] | None = None,
    ) -> RealtimeVoiceSession:
        session = RealtimeVoiceSession(
            session_id=session_id, agent_callback=agent_callback
        )
        self.sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> RealtimeVoiceSession | None:
        return self.sessions.get(session_id)

    async def close_session(self, session_id: str) -> None:
        session = self.sessions.pop(session_id, None)
        if session:
            await session.stop()
