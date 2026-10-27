import base64
import io
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


class ImageMetadata(BaseModel):
    """Metadata for an image file."""

    width: int = Field(default=0, description="Image width in pixels.")
    height: int = Field(default=0, description="Image height in pixels.")
    format: str = Field(
        default="JPEG", description="Image format (JPEG, PNG, WEBP, etc.)."
    )
    mime_type: str = Field(default="image/jpeg", description="MIME content type.")
    size_bytes: int = Field(default=0, description="File size in bytes.")


class ImageProcessor:
    """Processor for loading, resizing, compressing, and encoding images for vision LLMs."""

    def __init__(self, max_dimension: int = 1568, quality: int = 85):
        self.max_dimension = max_dimension
        self.quality = quality
        self._has_pil = False
        self._check_pil()

    def _check_pil(self) -> None:
        try:
            import PIL.Image  # noqa: F401, PLC0415

            self._has_pil = True
        except ImportError:
            self._has_pil = False

    def load_bytes(self, source: str | Path | bytes) -> tuple[bytes, str]:
        """Load image bytes and determine MIME type from a filepath, URL, or raw bytes."""
        if isinstance(source, bytes):
            mime = self._detect_mime(source)
            return source, mime

        path = Path(source)
        if path.exists() and path.is_file():
            with open(path, "rb") as f:
                content = f.read()
            mime = self._guess_mime_by_ext(path.suffix)
            return content, mime

        raise FileNotFoundError(f"Image source not found: {source}")

    def _guess_mime_by_ext(self, ext: str) -> str:
        ext = ext.lower().lstrip(".")
        if ext in ("png",):
            return "image/png"
        if ext in ("webp",):
            return "image/webp"
        if ext in ("gif",):
            return "image/gif"
        return "image/jpeg"

    def _detect_mime(self, data: bytes) -> str:
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
            return "image/gif"
        if len(data) > 12 and data[8:12] == b"WEBP":
            return "image/webp"
        return "image/jpeg"

    def get_metadata(self, data: bytes) -> ImageMetadata:
        """Extract metadata (dimensions, format, MIME) from image bytes."""
        mime = self._detect_mime(data)
        fmt = mime.split("/")[-1].upper()

        if self._has_pil:
            try:
                from PIL import Image  # noqa: PLC0415

                with Image.open(io.BytesIO(data)) as img:
                    return ImageMetadata(
                        width=img.width,
                        height=img.height,
                        format=img.format or fmt,
                        mime_type=mime,
                        size_bytes=len(data),
                    )
            except Exception as ex:
                logger.debug(f"Pillow metadata extraction failed: {ex}")

        return ImageMetadata(
            width=800, height=600, format=fmt, mime_type=mime, size_bytes=len(data)
        )

    def resize_and_compress(self, data: bytes) -> bytes:
        """Downscale image if larger than max_dimension and re-encode to compressed JPEG/PNG."""
        if not self._has_pil:
            return data

        try:
            from PIL import Image  # noqa: PLC0415

            with Image.open(io.BytesIO(data)) as img:
                # Maintain aspect ratio
                if img.width > self.max_dimension or img.height > self.max_dimension:
                    img.thumbnail(
                        (self.max_dimension, self.max_dimension),
                        Image.Resampling.LANCZOS,
                    )

                out_io = io.BytesIO()
                fmt = img.format if img.format in ("PNG", "WEBP") else "JPEG"
                if fmt == "JPEG":
                    img = img.convert("RGB")
                    img.save(out_io, format=fmt, quality=self.quality, optimize=True)
                else:
                    img.save(out_io, format=fmt, optimize=True)

                return out_io.getvalue()
        except Exception as ex:
            logger.error(f"Image resize/compression error: {ex}")
            return data

    def to_base64_data_url(self, data: bytes, mime_type: str | None = None) -> str:
        """Convert raw image bytes to a base64 Data URL (e.g. data:image/jpeg;base64,...)."""
        if not mime_type:
            mime_type = self._detect_mime(data)
        b64_str = base64.b64encode(data).decode("utf-8")
        return f"data:{mime_type};base64,{b64_str}"

    def to_vision_message_content(
        self, data: bytes, detail: str = "auto"
    ) -> dict[str, Any]:
        """Format image into standard OpenAI/ChatML vision content format."""
        compressed = self.resize_and_compress(data)
        data_url = self.to_base64_data_url(compressed)
        return {
            "type": "image_url",
            "image_url": {
                "url": data_url,
                "detail": detail,
            },
        }
