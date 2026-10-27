from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.multimodal.image import ImageProcessor
from amberclaw.multimodal.video import VideoProcessor


class AttachmentMedia(BaseModel):
    """Media attachment (image or video) from a channel or user message."""

    media_type: str = Field(..., description="Media type ('image' or 'video').")
    data_or_path: str | bytes = Field(..., description="File path, URL, or raw bytes.")
    mime_type: str | None = Field(default=None, description="Optional MIME type.")


class MultimodalRouter:
    """Router and formatter for constructing multimodal ChatML message payloads for vision LLMs."""

    def __init__(
        self,
        image_processor: ImageProcessor | None = None,
        video_processor: VideoProcessor | None = None,
    ):
        self.image_processor = image_processor or ImageProcessor()
        self.video_processor = video_processor or VideoProcessor(
            image_processor=self.image_processor
        )

    def create_multimodal_message(
        self,
        prompt_text: str,
        attachments: list[AttachmentMedia] | None = None,
        role: str = "user",
    ) -> dict[str, Any]:
        """Construct a standardized ChatML multimodal message payload containing text and vision media content."""
        content_items: list[dict[str, Any]] = []

        # Add text prompt content
        if prompt_text:
            content_items.append({"type": "text", "text": prompt_text})

        # Process attachments
        if attachments:
            for att in attachments:
                try:
                    if att.media_type == "image":
                        raw_bytes, mime = self.image_processor.load_bytes(
                            att.data_or_path
                        )
                        item = self.image_processor.to_vision_message_content(
                            raw_bytes, detail="auto"
                        )
                        content_items.append(item)
                    elif att.media_type == "video":
                        frame_items = self.video_processor.to_vision_frame_sequence(
                            att.data_or_path, max_frames=4
                        )
                        content_items.extend(frame_items)
                    else:
                        logger.warning(f"Unsupported media type: {att.media_type}")
                except Exception as ex:
                    logger.error(f"Error processing attachment {att.media_type}: {ex}")

        # If no multimodal attachments were added, format as simple text
        if len(content_items) == 1 and content_items[0]["type"] == "text":
            return {"role": role, "content": prompt_text}

        return {"role": role, "content": content_items}
