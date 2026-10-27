"""In-memory hybrid vector and keyword indexer for document chunks."""

import re
from collections import defaultdict

from loguru import logger

from amberclaw.rag.chunker import Chunk
from amberclaw.rag.embedder import cosine_similarity


class DocumentIndex:
    """Hybrid document index combining vector similarity and inverted keyword indexing."""

    def __init__(self) -> None:
        self._chunks: dict[str, Chunk] = {}
        self._embeddings: dict[str, list[float]] = {}
        self._inverted_index: dict[str, set[str]] = defaultdict(
            set
        )  # token -> set of chunk_ids

    @property
    def total_chunks(self) -> int:
        """Return total count of indexed chunks."""
        return len(self._chunks)

    def add_chunk(self, chunk: Chunk, embedding: list[float] | None = None) -> None:
        """Index a single document chunk."""
        self._chunks[chunk.chunk_id] = chunk
        if embedding is not None:
            self._embeddings[chunk.chunk_id] = embedding

        # Tokenize for keyword inverted index
        tokens = set(re.findall(r"\w+", chunk.text.lower()))
        for t in tokens:
            self._inverted_index[t].add(chunk.chunk_id)

    def add_chunks(
        self,
        chunks: list[Chunk],
        embeddings: list[list[float]] | None = None,
    ) -> None:
        """Batch index multiple chunks."""
        if embeddings and len(chunks) != len(embeddings):
            raise ValueError("Number of chunks must match number of embeddings")

        for idx, chunk in enumerate(chunks):
            emb = embeddings[idx] if embeddings else None
            self.add_chunk(chunk, emb)

        logger.info(
            "Indexed {} chunks into DocumentIndex (total: {})",
            len(chunks),
            self.total_chunks,
        )

    def get_chunk(self, chunk_id: str) -> Chunk | None:
        """Fetch chunk by identifier."""
        return self._chunks.get(chunk_id)

    def search_vector(
        self,
        query_vector: list[float],
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> list[tuple[Chunk, float]]:
        """Rank chunks by cosine similarity against query vector."""
        scores: list[tuple[Chunk, float]] = []
        for chunk_id, vec in self._embeddings.items():
            sim = cosine_similarity(query_vector, vec)
            if sim >= min_score:
                chunk = self._chunks[chunk_id]
                scores.append((chunk, sim))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def search_keyword(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[tuple[Chunk, float]]:
        """Rank chunks by keyword token overlap (Jaccard-like score)."""
        query_tokens = set(re.findall(r"\w+", query.lower()))
        if not query_tokens:
            return []

        chunk_matches: dict[str, int] = defaultdict(int)
        for t in query_tokens:
            for cid in self._inverted_index.get(t, set()):
                chunk_matches[cid] += 1

        results: list[tuple[Chunk, float]] = []
        for cid, match_count in chunk_matches.items():
            chunk = self._chunks[cid]
            # Keyword score: overlap normalized by query length
            score = match_count / len(query_tokens)
            results.append((chunk, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def clear(self) -> None:
        """Wipe index contents."""
        self._chunks.clear()
        self._embeddings.clear()
        self._inverted_index.clear()
