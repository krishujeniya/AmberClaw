"""Citation and source grounding utilities for RAG retrieval."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel


class Citation(BaseModel):
    """Structured citation metadata for retrieved context."""

    citation_index: int
    source: str
    chunk_id: str | None = None
    title: str | None = None
    snippet: str
    score: float | None = None


def format_grounded_context(docs: list[Any]) -> tuple[str, list[Citation]]:
    """Format documents into numbered citations and context block.

    Args:
        docs: List of Document objects or dicts with page_content and metadata.

    Returns:
        tuple[str, list[Citation]]: (formatted_context_block, citations)
    """
    citations: list[Citation] = []
    formatted_chunks: list[str] = []

    for idx, d in enumerate(docs, start=1):
        if hasattr(d, "page_content"):
            content = d.page_content.strip()
            meta = getattr(d, "metadata", {}) or {}
        elif isinstance(d, dict):
            content = str(d.get("content") or d.get("page_content") or "").strip()
            meta = d.get("metadata") or {}
        else:
            content = str(d).strip()
            meta = {}

        source = (
            meta.get("source")
            or meta.get("source_uri")
            or meta.get("url")
            or meta.get("session_id")
            or "memory"
        )
        chunk_id = meta.get("chunk_id") or meta.get("doc_id") or str(idx)
        title = meta.get("title") or meta.get("filename")

        citation = Citation(
            citation_index=idx,
            source=str(source),
            chunk_id=str(chunk_id),
            title=str(title) if title else None,
            snippet=content[:200],
            score=meta.get("score"),
        )
        citations.append(citation)

        header = f"[{idx}] Source: {source}"
        if title:
            header += f" ({title})"
        formatted_chunks.append(f"{header}\n{content}")

    context_block = "\n\n---\n\n".join(formatted_chunks)
    return context_block, citations


def verify_grounding(response_text: str, citations: list[Citation]) -> float:
    """Calculate a factual grounding score between response and source citations.

    Returns:
        float: Overlap score between 0.0 (ungrounded) and 1.0 (fully grounded).
    """
    if not response_text or not citations:
        return 0.0

    # Tokenize words (>3 chars)
    def _words(text: str) -> set[str]:
        return {w.lower() for w in re.findall(r"\b\w{4,}\b", text)}

    resp_words = _words(response_text)
    if not resp_words:
        return 1.0

    source_words: set[str] = set()
    for c in citations:
        source_words |= _words(c.snippet)

    overlap = resp_words.intersection(source_words)
    return len(overlap) / len(resp_words)
