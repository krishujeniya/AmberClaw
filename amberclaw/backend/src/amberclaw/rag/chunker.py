"""Document chunking and text segmentation algorithms for RAG pipelines."""

import uuid
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


class Chunk(BaseModel):
    """Segmented unit of text with positional metadata."""

    chunk_id: str = Field(default_factory=lambda: f"CHK-{uuid.uuid4().hex[:8]}")
    text: str = Field(..., description="The chunk text content")
    index: int = Field(
        default=0, ge=0, description="Sequential index within the document"
    )
    start_char: int = Field(default=0, ge=0)
    end_char: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TextChunker:
    """Configurable text chunker supporting sliding window overlap and whitespace boundary alignment."""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        separator: str = "\n\n",
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap cannot be negative")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be strictly less than chunk_size")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separator = separator

    def chunk_text(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """Split text into overlapping chunks, attempting to break cleanly on whitespace or paragraphs."""
        if not text.strip():
            return []

        chunks: list[Chunk] = []
        meta = metadata or {}
        pos = 0
        total_len = len(text)
        chunk_idx = 0

        while pos < total_len:
            end = min(pos + self.chunk_size, total_len)

            # If not at the very end of text, attempt to find a clean word or paragraph boundary
            if end < total_len:
                # Look backwards for a separator or newline or space
                boundary = text.rfind(self.separator, pos + self.chunk_overlap, end)
                if boundary == -1:
                    boundary = text.rfind(" ", pos + self.chunk_overlap, end)

                if boundary != -1 and boundary > pos:
                    end = boundary

            chunk_content = text[pos:end].strip()
            if chunk_content:
                chunks.append(
                    Chunk(
                        text=chunk_content,
                        index=chunk_idx,
                        start_char=pos,
                        end_char=end,
                        metadata=meta.copy(),
                    )
                )
                chunk_idx += 1

            if end >= total_len:
                break

            # Slide forward by (chunk_size - chunk_overlap)
            step = max(1, (end - pos) - self.chunk_overlap)
            pos += step

        logger.debug(
            "Segmented text of length {} into {} chunks", total_len, len(chunks)
        )
        return chunks

    def chunk_documents(
        self,
        docs: list[dict[str, Any]],
        text_field: str = "content",
    ) -> list[Chunk]:
        """Batch process a list of document dictionaries containing text and metadata."""
        all_chunks: list[Chunk] = []
        for doc in docs:
            text = doc.get(text_field, "")
            doc_meta = {k: v for k, v in doc.items() if k != text_field}
            all_chunks.extend(self.chunk_text(text, metadata=doc_meta))
        return all_chunks
