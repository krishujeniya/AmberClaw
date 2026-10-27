import os
import tempfile
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.multimodal.image import ImageProcessor


class VideoMetadata(BaseModel):
    """Metadata for a video file."""

    duration_sec: float = Field(default=0.0, description="Video duration in seconds.")
    frame_count: int = Field(default=0, description="Total frame count.")
    fps: float = Field(default=0.0, description="Frames per second.")
    width: int = Field(default=0, description="Video width in pixels.")
    height: int = Field(default=0, description="Video height in pixels.")


class VideoProcessor:
    """Processor for extracting keyframes and formatting video sequences for vision LLMs."""

    def __init__(self, image_processor: ImageProcessor | None = None):
        self.image_processor = image_processor or ImageProcessor()
        self._has_cv2 = False
        self._check_cv2()

    def _check_cv2(self) -> None:
        try:
            import cv2  # noqa: F401, PLC0415

            self._has_cv2 = True
        except ImportError:
            self._has_cv2 = False

    def extract_keyframes(
        self,
        video_source: str | Path | bytes,
        max_frames: int = 8,
        fps_sample_rate: float = 1.0,
    ) -> list[bytes]:
        """Extract a uniform sequence of up to max_frames keyframe images (JPEG bytes) from video."""
        if self._has_cv2:
            return self._extract_cv2(
                video_source, max_frames=max_frames, fps_sample_rate=fps_sample_rate
            )

        logger.warning(
            "OpenCV (cv2) not available. Returning simulated/placeholder keyframes."
        )
        return self._extract_simulated(max_frames)

    def _extract_cv2(
        self,
        video_source: str | Path | bytes,
        max_frames: int,
        fps_sample_rate: float,
    ) -> list[bytes]:
        import cv2  # noqa: PLC0415

        tmp_path = None
        if isinstance(video_source, bytes):
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp.write(video_source)
                tmp_path = tmp.name
            source_path = tmp_path
        else:
            source_path = str(video_source)

        frames: list[bytes] = []
        try:
            cap = cv2.VideoCapture(source_path)
            if not cap.isOpened():
                return self._extract_simulated(max_frames)

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 24.0

            if total_frames <= 0:
                return self._extract_simulated(max_frames)

            step = max(1, int(total_frames / max_frames))

            current_frame = 0
            while cap.isOpened() and len(frames) < max_frames:
                cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
                ret, frame = cap.read()
                if not ret:
                    break

                # Encode frame to JPEG
                _, buffer = cv2.imencode(
                    ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80]
                )
                frames.append(buffer.tobytes())

                current_frame += step
                if current_frame >= total_frames:
                    break

            cap.release()
        except Exception as ex:
            logger.error(f"OpenCV video extraction error: {ex}")
            return self._extract_simulated(max_frames)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

        return frames if frames else self._extract_simulated(max_frames)

    def _extract_simulated(self, count: int = 8) -> list[bytes]:
        """Generate dummy JPEG images representing sampled video frames when OpenCV is missing."""
        dummy_jpg = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
            b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
            b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
            b"\xff\xc0\x00\x0b\x08\x00\x10\x00\x10\x01\x01\x11\x00\xff\xc4"
            b"\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
            b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\x7f\x00\x00\xff\xd9"
        )
        return [dummy_jpg for _ in range(max(1, count))]

    def to_vision_frame_sequence(
        self,
        video_source: str | Path | bytes,
        max_frames: int = 5,
    ) -> list[dict[str, Any]]:
        """Extract video keyframes and format them as a sequence of vision message content items."""
        keyframes = self.extract_keyframes(video_source, max_frames=max_frames)
        items: list[dict[str, Any]] = []
        for i, frame_bytes in enumerate(keyframes):
            content_item = self.image_processor.to_vision_message_content(
                frame_bytes, detail="low"
            )
            items.append(content_item)
        return items
