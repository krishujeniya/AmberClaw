"""AmberClaw Knowledge RAG tools.

Hybrid RAG implementation using:
1. BM25/TF-IDF (Keyword search via scikit-learn)
2. Vector Similarity (Dense search via LiteLLM embeddings)
3. Reranking (Cross-encoder via LiteLLM or RRF fusion)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger
from numpy.typing import NDArray
from pydantic import BaseModel, Field

# sklearn imports moved to lazy imports in KnowledgeSearchTool.run
from amberclaw.agent.tools.base import PydanticTool
from amberclaw.providers.base import LLMProvider


class KnowledgeSearchArgs(BaseModel):
    """Arguments for knowledge search."""

    query: str = Field(..., description="The query to search in your knowledge base.")
    limit: int = Field(default=3, description="Maximum number of results.")


class KnowledgeAddArgs(BaseModel):
    """Arguments for adding knowledge."""

    content: str = Field(..., description="The information to store.")
    tags: list[str] = Field(default_factory=list, description="Optional tags.")


class KnowledgeToolBase(PydanticTool):
    def __init__(
        self,
        workspace: Path | None = None,
        provider: LLMProvider | None = None,
        embedding_model: str = "openai/text-embedding-3-small",
        reranker_model: str | None = None,
    ) -> None:
        super().__init__()
        self.workspace = workspace or Path.home() / ".amberclaw" / "workspace"
        self.kb_path = self.workspace / "knowledge_base.json"
        self.vectors_path = self.workspace / "knowledge_base.vectors.npy"
        self.provider = provider
        self.embedding_model = embedding_model
        self.reranker_model = reranker_model
        self.workspace.mkdir(parents=True, exist_ok=True)

        if not self.kb_path.exists():
            self.kb_path.write_text(json.dumps({"entries": []}))

    def _load_kb(self) -> dict[str, Any]:
        try:
            data = json.loads(self.kb_path.read_text())
            if isinstance(data, dict) and isinstance(data.get("entries"), list):
                return data
            return {"entries": []}
        except Exception:
            return {"entries": []}

    def _save_kb(self, kb: dict[str, Any]) -> None:
        self.kb_path.write_text(json.dumps(kb, indent=2))

    def _load_vectors(self) -> NDArray[np.float64] | None:
        if self.vectors_path.exists():
            try:
                vectors = np.load(self.vectors_path, allow_pickle=False)
                if isinstance(vectors, np.ndarray):
                    return np.asarray(vectors, dtype=np.float64)
            except Exception as e:
                logger.error("Failed to load knowledge vectors: {}", e)
        return None

    def _save_vectors(self, vectors: NDArray[np.float64]) -> None:
        np.save(self.vectors_path, vectors)

    async def _get_embedding(self, text: str) -> NDArray[np.float64]:
        """Get embedding for text using the configured provider."""
        if not self.provider:
            # Try to return a zero vector of common dimension (e.g., 1536 for OpenAI)
            # as a last resort, but better to warn.
            logger.warning(
                "No provider configured for KnowledgeTool. Returning zero vector."
            )
            return np.zeros(1536)

        import litellm  # noqa: PLC0415 - load the optional runtime dependency only for this operation

        try:
            response = await litellm.aembedding(
                model=self.embedding_model, input=[text]
            )
            # Handle both object (litellm standard) and dict (some fallbacks)
            data = getattr(response, "data", [])
            if not data and isinstance(response, dict):
                data = response.get("data", [])

            if not data:
                logger.error("Empty embedding response from LiteLLM")
                return np.zeros(1536)

            item = data[0]
            embedding = getattr(item, "embedding", None)
            if embedding is None and isinstance(item, dict):
                embedding = item.get("embedding")

            if embedding is None:
                logger.error("Could not extract embedding from LiteLLM response")
                return np.zeros(1536)

            return np.array(embedding)
        except Exception as e:
            logger.error("Embedding failed for model {}: {}", self.embedding_model, e)
            return np.zeros(1536)


class KnowledgeSearchTool(KnowledgeToolBase):
    """Search your local personal knowledge base using Hybrid RAG."""

    @property
    def name(self) -> str:
        return "knowledge_search"

    @property
    def description(self) -> str:
        return (
            "Advanced search through indexed information in your local knowledge base. "
            "Uses keyword (BM25) and semantic similarity (vectors) for high recall."
        )

    @property
    def args_schema(self) -> type[KnowledgeSearchArgs]:
        return KnowledgeSearchArgs

    async def run(self, args: KnowledgeSearchArgs) -> str:
        kb = self._load_kb()
        entries = kb.get("entries", [])
        if not entries:
            return "Knowledge base is empty."

        corpus = [e["content"] for e in entries]

        keyword_scores = self._keyword_scores(corpus, args.query)
        semantic_scores = await self._semantic_scores(corpus, args.query)

        # 3. Fusion (Reciprocal Rank Fusion)
        # Sort by scores to get ranks
        kw_ranks = np.argsort(np.argsort(-keyword_scores))  # Rank 0 is best
        sem_ranks = np.argsort(np.argsort(-semantic_scores))

        # RRF formula: Score = sum(1 / (k + rank))
        k = 60
        fused_scores = (1.0 / (k + kw_ranks)) + (1.0 / (k + sem_ranks))

        # Top-K indices
        top_indices = np.argsort(-fused_scores)[
            : args.limit * 2
        ]  # Get more for reranking
        candidate_entries = [entries[i] for i in top_indices]

        final_results = await self._rerank(candidate_entries, args)

        if not final_results:
            return "No matching knowledge found."

        formatted = []
        for i, res in enumerate(final_results):
            tags = (
                f" [tags: {', '.join(res.get('tags', []))}]" if res.get("tags") else ""
            )
            formatted.append(f"Result {i + 1}:\n{res['content']}{tags}")

        return "\n---\n".join(formatted)

    @staticmethod
    def _keyword_scores(corpus: list[str], query: str) -> NDArray[np.float64]:
        try:
            from sklearn.feature_extraction.text import (  # noqa: PLC0415 - optional search backend
                TfidfVectorizer,
            )
            from sklearn.metrics.pairwise import (  # noqa: PLC0415 - optional search backend
                cosine_similarity,
            )

            vectorizer = TfidfVectorizer(stop_words="english")
            matrix = vectorizer.fit_transform(corpus)
            query_vector = vectorizer.transform([query])
            return np.asarray(
                cosine_similarity(query_vector, matrix).flatten(), dtype=np.float64
            )
        except (ImportError, ValueError):
            return np.zeros(len(corpus))

    async def _semantic_scores(
        self, corpus: list[str], query: str
    ) -> NDArray[np.float64]:
        vectors = self._load_vectors()
        if vectors is None or len(vectors) != len(corpus):
            return np.zeros(len(corpus))
        query_embedding = await self._get_embedding(query)
        if query_embedding.shape != vectors[0].shape:
            return np.zeros(len(corpus))
        norms = np.linalg.norm(vectors, axis=1) * np.linalg.norm(query_embedding)
        return np.asarray(
            np.divide(
                np.dot(vectors, query_embedding),
                norms,
                out=np.zeros(len(corpus)),
                where=norms > 0,
            ),
            dtype=np.float64,
        )

    async def _rerank(
        self, candidates: list[dict[str, Any]], args: KnowledgeSearchArgs
    ) -> list[dict[str, Any]]:
        if not self.reranker_model or not self.provider:
            return candidates[: args.limit]
        import litellm  # noqa: PLC0415 - optional reranking backend

        try:
            response = await litellm.arerank(
                model=self.reranker_model,
                query=args.query,
                documents=[entry["content"] for entry in candidates],
                top_n=args.limit,
            )
            indices = (
                getattr(result, "index", None)
                for result in getattr(response, "results", [])
            )
            return [
                candidates[index]
                for index in indices
                if isinstance(index, int) and 0 <= index < len(candidates)
            ]
        except Exception as exc:
            logger.debug("Reranking failed: {}. Falling back to fusion results.", exc)
            return candidates[: args.limit]


class KnowledgeAddTool(KnowledgeToolBase):
    """Add information to your local personal knowledge base with vector indexing."""

    @property
    def name(self) -> str:
        return "knowledge_add"

    @property
    def description(self) -> str:
        return "Save new information, facts, or notes. Automatically indexes for semantic search."

    @property
    def args_schema(self) -> type[KnowledgeAddArgs]:
        return KnowledgeAddArgs

    async def run(self, args: KnowledgeAddArgs) -> str:
        kb = self._load_kb()

        # Compute embedding
        logger.info("Indexing new knowledge entry...")
        vector = await self._get_embedding(args.content)

        kb["entries"].append(
            {
                "content": args.content,
                "tags": args.tags,
            },
        )

        # Update vector store
        existing_vectors = self._load_vectors()
        if existing_vectors is not None:
            if existing_vectors.shape[1] == vector.shape[0]:
                new_vectors = np.vstack([existing_vectors, vector])
            else:
                # Shape mismatch (model changed?) - rebuild index (simple for MVP)
                logger.warning("Vector dimension mismatch. Rebuilding index...")
                vectors = []
                for entry in kb["entries"]:
                    v = await self._get_embedding(entry["content"])
                    vectors.append(v)
                new_vectors = np.array(vectors)
        else:
            new_vectors = np.array([vector])

        self._save_kb(kb)
        self._save_vectors(new_vectors)

        return f"Successfully added and indexed knowledge: {args.content[:50]}..."
