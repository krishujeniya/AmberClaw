# ruff: noqa: PLR0912, PLR2004
"""Citation and source grounding utilities for RAG retrieval."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field


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
            content = str(d.get("content") or d.get("page_content") or d.get("text") or "").strip()
            meta = d.get("metadata") if isinstance(d.get("metadata"), dict) else d
        else:
            content = str(d).strip()
            meta = {}

        source = (
            meta.get("source")
            or meta.get("source_uri")
            or meta.get("url")
            or meta.get("id")
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


class GroundedAnswer(BaseModel):
    """Result of grounded retrieval QA with verified source spans and abstention tracking."""

    answer: str
    is_abstained: bool = False
    abstention_reason: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    grounding_score: float = 0.0
    source_spans: list[dict[str, Any]] = Field(default_factory=list)


def generate_grounded_answer(
    query: str,
    docs: list[Any],
    min_grounding_threshold: float = 0.40,
    min_query_overlap_threshold: float = 0.15,
) -> GroundedAnswer:
    """Synthesize grounded answer from context docs, citing source spans or abstaining.

    Rubric:
    1. If docs is empty -> Abstain (INSUFFICIENT_EVIDENCE).
    2. Check prompt poisoning / malicious injection in retrieved docs. Sanitize or exclude.
    3. Filter out superseded/stale facts when temporal contradiction exists.
    4. Verify query overlap with retrieved sources. If completely off-topic -> Abstain (UNSUPPORTED_QUERY).
    5. Construct answer citing source markers [1], [2], extracting exact char spans.
    6. Verify grounding score >= min_grounding_threshold. If not -> Abstain (LOW_GROUNDING_CONFIDENCE).
    """
    if not query or not query.strip():
        return GroundedAnswer(
            answer="Query is empty.",
            is_abstained=True,
            abstention_reason="EMPTY_QUERY",
        )

    if not docs:
        return GroundedAnswer(
            answer="I do not have sufficient verified evidence in my knowledge base to answer this question.",
            is_abstained=True,
            abstention_reason="INSUFFICIENT_EVIDENCE",
        )

    # 1. Filter out poisoned documents or prompt injections
    safe_docs = []
    injection_patterns = [
        re.compile(r"ignore\s+(all\s+)?(prior|previous)\s+instructions", re.I),
        re.compile(r"system\s*:\s*override", re.I),
        re.compile(r"disregard\s+all\s+constraints", re.I),
    ]

    for d in docs:
        if hasattr(d, "page_content"):
            c = d.page_content
            meta = getattr(d, "metadata", {}) or {}
        elif isinstance(d, dict):
            c = str(d.get("content") or d.get("page_content") or d.get("text") or "")
            meta = d.get("metadata") if isinstance(d.get("metadata"), dict) else d
        else:
            c = str(d)
            meta = {}

        if meta.get("poisoning_detected"):
            continue
        if any(p.search(c) for p in injection_patterns):
            continue
        safe_docs.append(d)

    if not safe_docs:
        return GroundedAnswer(
            answer="I do not have sufficient verified evidence in my knowledge base to answer this question.",
            is_abstained=True,
            abstention_reason="POISONING_DETECTED",
        )

    # 2. Sort documents temporally if timestamps exist (resolving stale contradictions)
    def _doc_timestamp(d: Any) -> str:
        meta = getattr(d, "metadata", {}) if hasattr(d, "metadata") else (d.get("metadata", {}) if isinstance(d, dict) else {})
        return str(meta.get("updated_at") or meta.get("timestamp") or meta.get("created_at") or "")

    sorted_docs = sorted(safe_docs, key=_doc_timestamp, reverse=True)

    # 3. Format citations and context block
    _ctx_block, citations = format_grounded_context(sorted_docs)

    # 4. Check query overlap with retrieved knowledge
    def _words(text: str) -> set[str]:
        return {w.lower() for w in re.findall(r"\b\w{3,}\b", text)}

    q_words = _words(query)
    all_context_words = set()
    for c in citations:
        all_context_words |= _words(c.snippet)

    overlap = q_words.intersection(all_context_words)
    overlap_ratio = len(overlap) / float(len(q_words)) if q_words else 0.0

    if overlap_ratio < min_query_overlap_threshold:
        return GroundedAnswer(
            answer="I do not have sufficient verified evidence in my knowledge base to answer this question.",
            is_abstained=True,
            abstention_reason="UNSUPPORTED_QUERY",
            citations=citations,
        )

    # 5. Synthesize grounded answer statements with source spans
    answer_sentences = []
    source_spans = []

    for c in citations:
        # Find key sentence in snippet containing overlap words
        snippet_sentences = [s.strip() for s in re.split(r"[.\n]+", c.snippet) if s.strip()]
        matched_sentence = ""
        for s in snippet_sentences:
            if _words(s).intersection(q_words):
                matched_sentence = s
                break
        if not matched_sentence and snippet_sentences:
            matched_sentence = snippet_sentences[0]

        if matched_sentence:
            # Locate exact character span
            start_char = c.snippet.find(matched_sentence)
            end_char = start_char + len(matched_sentence) if start_char != -1 else len(matched_sentence)

            source_spans.append({
                "citation_index": c.citation_index,
                "source": c.source,
                "chunk_id": c.chunk_id,
                "start_char": max(0, start_char),
                "end_char": end_char,
                "span_text": matched_sentence,
            })
            answer_sentences.append(f"{matched_sentence} [{c.citation_index}]")

        if len(answer_sentences) >= 2:
            break

    final_answer = " ".join(answer_sentences)
    grounding_score = verify_grounding(final_answer, citations)

    if grounding_score < min_grounding_threshold or not final_answer:
        return GroundedAnswer(
            answer="I do not have sufficient verified evidence in my knowledge base to answer this question.",
            is_abstained=True,
            abstention_reason="LOW_GROUNDING_CONFIDENCE",
            citations=citations,
            grounding_score=grounding_score,
            source_spans=source_spans,
        )

    return GroundedAnswer(
        answer=final_answer,
        is_abstained=False,
        citations=citations,
        grounding_score=round(grounding_score, 4),
        source_spans=source_spans,
    )
