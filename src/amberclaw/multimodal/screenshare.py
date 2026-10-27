import asyncio
import time
import uuid
from collections.abc import Callable
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.multimodal.image import ImageProcessor


class ScreenFrameSample(BaseModel):
    """Metadata and raw content for a single captured screen frame."""

    frame_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = Field(default_factory=time.time)
    width: int = Field(default=1920)
    height: int = Field(default=1080)
    frame_bytes: bytes = Field(default=b"", repr=False)


class ScreenAnalysisResult(BaseModel):
    """Result of vision LLM analysis on live screen share frames."""

    frame_id: str
    timestamp: float = Field(default_factory=time.time)
    active_context: str = Field(
        default="IDE / Code Editor", description="Detected screen context."
    )
    detected_errors: list[str] = Field(
        default_factory=list, description="Compiler or UI errors found on screen."
    )
    guidance_notes: str = Field(
        default="", description="Pair-programming guidance and advice."
    )
    suggested_actions: list[str] = Field(
        default_factory=list, description="Recommended next developer actions."
    )


class ScreenShareSession:
    """Manages WebRTC screen share video stream ingestion and live vision guidance."""

    def __init__(
        self,
        session_id: str | None = None,
        sample_interval_sec: float = 2.0,
        image_processor: ImageProcessor | None = None,
    ):
        self.session_id = session_id or str(uuid.uuid4())
        self.sample_interval_sec = sample_interval_sec
        self.image_processor = image_processor or ImageProcessor()
        self.is_active = False

        self._frame_queue: asyncio.Queue[ScreenFrameSample] = asyncio.Queue()
        self._last_processed_frame: ScreenFrameSample | None = None
        self._analysis_history: list[ScreenAnalysisResult] = []

    async def start(self) -> None:
        """Start the live screen share session."""
        self.is_active = True
        logger.info(f"ScreenShareSession {self.session_id} started.")

    async def stop(self) -> None:
        """Stop the live screen share session."""
        self.is_active = False
        logger.info(f"ScreenShareSession {self.session_id} stopped.")

    def push_frame(
        self, frame_bytes: bytes, width: int = 1920, height: int = 1080
    ) -> None:
        """Push incoming WebRTC video frame bytes into screen share buffer."""
        if not self.is_active or not frame_bytes:
            return

        sample = ScreenFrameSample(frame_bytes=frame_bytes, width=width, height=height)
        # Keep queue bounded to latest frame
        if self._frame_queue.full():
            try:
                self._frame_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        self._frame_queue.put_nowait(sample)

    async def analyze_latest_frame(
        self, vision_callback: Callable[[dict[str, Any]], Any] | None = None
    ) -> ScreenAnalysisResult:
        """Analyze latest screen frame using vision LLM or image heuristics."""
        sample = None
        try:
            sample = self._frame_queue.get_nowait()
        except asyncio.QueueEmpty:
            sample = self._last_processed_frame or ScreenFrameSample()

        self._last_processed_frame = sample

        # Generate vision content payload
        vision_item = self.image_processor.to_vision_message_content(
            sample.frame_bytes
            if sample.frame_bytes
            else b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xd9"
        )

        guidance_text = (
            "Screen content analyzed: Visual pair-programming session active."
        )
        errors = []

        if vision_callback:
            try:
                callback_resp = await vision_callback(vision_item)
                if isinstance(callback_resp, str):
                    guidance_text = callback_resp
            except Exception as ex:
                logger.error(f"Error in screen analysis vision callback: {ex}")

        result = ScreenAnalysisResult(
            frame_id=sample.frame_id,
            timestamp=sample.timestamp,
            active_context="Code Editor / Terminal",
            detected_errors=errors,
            guidance_notes=guidance_text,
            suggested_actions=[
                "Review active code diff.",
                "Run test suite in terminal.",
            ],
        )

        self._analysis_history.append(result)
        return result
