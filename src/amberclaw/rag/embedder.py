"""Embedding generation abstractions and deterministic vector projection utilities."""

import hashlib
import math
from abc import ABC, abstractmethod

from loguru import logger
from pydantic import BaseModel, Field


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if len(vec_a) != len(vec_b) or not vec_a:
        return 0.0

    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class EmbeddingResult(BaseModel):
    """Vector representation resulting from text embedding."""

    text: str
    embedding: list[float]
    dimensions: int = Field(default=64, ge=1)


MIN_DIMENSIONS: int = 8
MIN_NGRAM_WORD_LEN: int = 3


class BaseEmbedder(ABC):
    """Abstract interface for text embedding engines."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Convert a single text string into a normalized dense vector."""
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Batch convert a sequence of text strings into normalized vectors."""
        pass


class DeterministicHashEmbedder(BaseEmbedder):
    """Lightweight, deterministic n-gram hashing embedder suitable for testing and offline retrieval."""

    def __init__(self, dimensions: int = 64) -> None:
        if dimensions < MIN_DIMENSIONS:
            raise ValueError(f"dimensions must be at least {MIN_DIMENSIONS}")
        self.dimensions = dimensions

    def embed_text(self, text: str) -> list[float]:
        """Generate a normalized dense vector using character n-gram bucket hashing."""
        vec = [0.0] * self.dimensions
        cleaned = text.lower().strip()
        if not cleaned:
            return vec

        # Tokenize by words and character 3-grams
        words = cleaned.split()
        tokens = list(words)
        for w in words:
            if len(w) >= MIN_NGRAM_WORD_LEN:
                tokens.extend(w[i : i + 3] for i in range(len(w) - 2))

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dimensions
            val = ((digest[4] % 100) / 50.0) - 1.0  # Float in [-1.0, 1.0]
            vec[idx] += val

        # L2 Normalize
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0.0:
            vec = [v / norm for v in vec]

        return vec

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Batch vectorize multiple texts."""
        logger.debug("Generating embeddings for batch of {} texts", len(texts))
        return [self.embed_text(t) for t in texts]
