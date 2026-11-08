"""Data-science text embedding entry point.

Embedding implementations live once in :mod:`amberclaw.rag.embedder`. This
module re-exports them so data-science pipelines share the same embedders and
similarity maths as the rest of AmberClaw.
"""

from amberclaw.rag.embedder import (
    BaseEmbedder,
    DeterministicHashEmbedder,
    EmbeddingResult,
    cosine_similarity,
)

__all__ = [
    "BaseEmbedder",
    "DeterministicHashEmbedder",
    "EmbeddingResult",
    "cosine_similarity",
]
