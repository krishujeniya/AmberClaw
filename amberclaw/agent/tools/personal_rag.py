"""AmberClaw Knowledge RAG tools.

Hybrid RAG implementation using:
1. BM25/TF-IDF (Keyword search via scikit-learn)
2. Vector Similarity (Dense search via LiteLLM embeddings)
3. Reranking (Cross-encoder via LiteLLM or RRF fusion)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

import numpy as np
from loguru import logger
from pydantic import BaseModel, Field
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from amberclaw.agent.tools.base import PydanticTool
from amberclaw.providers.base import LLMProvider


class KnowledgeSearchArgs(BaseModel):
    """Arguments for knowledge search."""

    query: str = Field(..., description="The query to search in your knowledge base.")
    limit: int = Field(default=3, description="Maximum number of results.")


class KnowledgeAddArgs(BaseModel):
    """Arguments for adding knowledge."""

    content: str = Field(..., description="The information to store.")
    tags: List[str] = Field(default_factory=list, description="Optional tags.")


class KnowledgeToolBase(PydanticTool):
    def __init__(
        self,
        workspace: Path | None = None,
        provider: LLMProvider | None = None,
        embedding_model: str = "openai/text-embedding-3-small",
        reranker_model: str | None = None,
    ):
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

    def _load_kb(self) -> dict:
        try:
            return json.loads(self.kb_path.read_text())
        except Exception:
            return {"entries": []}

    def _save_kb(self, kb: dict):
        self.kb_path.write_text(json.dumps(kb, indent=2))

    def _load_vectors(self) -> np.ndarray | None:
        if self.vectors_path.exists():
            try:
                return np.load(self.vectors_path)
            except Exception as e:
                logger.error("Failed to load knowledge vectors: {}", e)
        return None

    def _save_vectors(self, vectors: np.ndarray):
        np.save(self.vectors_path, vectors)

    async def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding for text using the configured provider."""
        if not self.provider:
            return np.zeros(1)  # Fallback if no provider

        # LiteLLM embedding call
        import litellm

        try:
            response = await litellm.aembedding(model=self.embedding_model, input=[text])
            return np.array(response.data[0]["embedding"])
        except Exception as e:
            logger.error("Embedding failed for model {}: {}", self.embedding_model, e)
            return np.zeros(1)


class KnowledgeSearchTool(KnowledgeToolBase):
    """Search your local personal knowledge base using Hybrid RAG."""

    name = "knowledge_search"
    description = (
        "Advanced search through indexed information in your local knowledge base. "
        "Uses keyword (BM25) and semantic similarity (vectors) for high recall."
    )
    args_schema = KnowledgeSearchArgs

    async def run(self, args: KnowledgeSearchArgs) -> str:
        kb = self._load_kb()
        entries = kb.get("entries", [])
        if not entries:
            return "Knowledge base is empty."

        corpus = [e["content"] for e in entries]

        # 1. Keyword Search (TF-IDF as proxy for BM25)
        vectorizer = TfidfVectorizer(stop_words="english")
        try:
            tfidf_matrix = vectorizer.fit_transform(corpus)
            query_vec = vectorizer.transform([args.query])
            keyword_scores = cosine_similarity(query_vec, tfidf_matrix).flatten()
        except ValueError:  # Empty corpus or stop words issue
            keyword_scores = np.zeros(len(corpus))

        # 2. Vector Search (Semantic)
        vectors = self._load_vectors()
        if vectors is not None and len(vectors) == len(corpus):
            query_embedding = await self._get_embedding(args.query)
            if query_embedding.shape == vectors[0].shape:
                semantic_scores = cosine_similarity(
                    query_embedding.reshape(1, -1), vectors
                ).flatten()
            else:
                semantic_scores = np.zeros(len(corpus))
        else:
            semantic_scores = np.zeros(len(corpus))

        # 3. Fusion (Reciprocal Rank Fusion)
        # Sort by scores to get ranks
        kw_ranks = np.argsort(np.argsort(-keyword_scores))  # Rank 0 is best
        sem_ranks = np.argsort(np.argsort(-semantic_scores))

        # RRF formula: Score = sum(1 / (k + rank))
        k = 60
        fused_scores = (1.0 / (k + kw_ranks)) + (1.0 / (k + sem_ranks))

        # Top-K indices
        top_indices = np.argsort(-fused_scores)[: args.limit * 2]  # Get more for reranking
        candidate_entries = [entries[i] for i in top_indices]

        # 4. Reranking (optional)
        final_results = []
        if self.reranker_model and self.provider:
            import litellm

            try:
                # LiteLLM rerank (if supported by provider)
                rerank_resp = await litellm.arerank(
                    model=self.reranker_model,
                    query=args.query,
                    documents=[e["content"] for e in candidate_entries],
                    top_n=args.limit,
                )
                for res in rerank_resp.results:
                    final_results.append(candidate_entries[res.index])
            except Exception as e:
                logger.debug("Reranking failed: {}. Falling back to fusion results.", e)
                final_results = candidate_entries[: args.limit]
        else:
            final_results = candidate_entries[: args.limit]

        if not final_results:
            return "No matching knowledge found."

        formatted = []
        for i, res in enumerate(final_results):
            tags = f" [tags: {', '.join(res.get('tags', []))}]" if res.get("tags") else ""
            formatted.append(f"Result {i + 1}:\n{res['content']}{tags}")

        return "\n---\n".join(formatted)


class KnowledgeAddTool(KnowledgeToolBase):
    """Add information to your local personal knowledge base with vector indexing."""

    name = "knowledge_add"
    description = (
        "Save new information, facts, or notes. Automatically indexes for semantic search."
    )
    args_schema = KnowledgeAddArgs

    async def run(self, args: KnowledgeAddArgs) -> str:
        kb = self._load_kb()

        # Compute embedding
        logger.info("Indexing new knowledge entry...")
        vector = await self._get_embedding(args.content)

        kb["entries"].append(
            {
                "content": args.content,
                "tags": args.tags,
            }
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
