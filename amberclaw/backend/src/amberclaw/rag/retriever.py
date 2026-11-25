"""Hybrid document retrieval using reciprocal rank fusion and vector ranking."""

from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.rag.chunker import Chunk
from amberclaw.rag.embedder import BaseEmbedder, DeterministicHashEmbedder
from amberclaw.rag.indexer import DocumentIndex


class RetrievalResult(BaseModel):
    """Scored document chunk returned by a retriever."""

    chunk: Chunk
    score: float = Field(..., ge=0.0)
    retrieval_method: str = Field(default="hybrid")


class DocumentRetriever:
    """Retrieves and ranks relevant document chunks using hybrid vector and lexical search."""

    def __init__(
        self,
        index: DocumentIndex,
        embedder: BaseEmbedder | None = None,
    ) -> None:
        self.index = index
        self.embedder = embedder or DeterministicHashEmbedder()

    def retrieve_vector(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        """Perform dense vector retrieval for the query."""
        q_vec = self.embedder.embed_text(query)
        matches = self.index.search_vector(q_vec, top_k=top_k)
        return [
            RetrievalResult(
                chunk=chunk, score=round(score, 4), retrieval_method="vector"
            )
            for chunk, score in matches
        ]

    def retrieve_keyword(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        """Perform sparse keyword overlap retrieval for the query."""
        matches = self.index.search_keyword(query, top_k=top_k)
        return [
            RetrievalResult(
                chunk=chunk, score=round(score, 4), retrieval_method="keyword"
            )
            for chunk, score in matches
        ]

    def retrieve_hybrid(
        self,
        query: str,
        top_k: int = 5,
        vector_weight: float = 0.6,
        rrf_k: int = 60,
    ) -> list[RetrievalResult]:
        """Combine dense vector search and sparse keyword search via Reciprocal Rank Fusion (RRF)."""
        vec_results = self.retrieve_vector(query, top_k=top_k * 2)
        kw_results = self.retrieve_keyword(query, top_k=top_k * 2)

        rrf_scores: dict[str, float] = {}
        chunk_map: dict[str, Chunk] = {}

        # Vector RRF
        for rank, res in enumerate(vec_results):
            cid = res.chunk.chunk_id
            chunk_map[cid] = res.chunk
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + vector_weight * (
                1.0 / (rrf_k + rank + 1)
            )

        # Keyword RRF
        kw_weight = 1.0 - vector_weight
        for rank, res in enumerate(kw_results):
            cid = res.chunk.chunk_id
            chunk_map[cid] = res.chunk
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + kw_weight * (
                1.0 / (rrf_k + rank + 1)
            )

        ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        logger.debug(
            "Hybrid retrieval for '{}' returned {} results", query, len(ranked)
        )

        return [
            RetrievalResult(
                chunk=chunk_map[cid],
                score=round(score * 100, 4),  # Scaled for readability
                retrieval_method="hybrid_rrf",
            )
            for cid, score in ranked
        ]
