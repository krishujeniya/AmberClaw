"""AmberClaw Retrieval-Augmented Generation (RAG) subsystem."""

from pydantic import BaseModel, Field

from amberclaw.rag.chunker import Chunk, TextChunker
from amberclaw.rag.embedder import (
    BaseEmbedder,
    DeterministicHashEmbedder,
    EmbeddingResult,
    cosine_similarity,
)
from amberclaw.rag.indexer import DocumentIndex
from amberclaw.rag.knowledge_base import KnowledgeBase
from amberclaw.rag.retriever import DocumentRetriever, RetrievalResult


class RagModuleConfig(BaseModel):
    """Configuration for the amberclaw.rag module."""

    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")
    default_chunk_size: int = Field(default=400, ge=50)
    default_chunk_overlap: int = Field(default=40, ge=0)


__all__ = [
    "BaseEmbedder",
    "Chunk",
    "DeterministicHashEmbedder",
    "DocumentIndex",
    "DocumentRetriever",
    "EmbeddingResult",
    "KnowledgeBase",
    "RagModuleConfig",
    "RetrievalResult",
    "TextChunker",
    "cosine_similarity",
]
