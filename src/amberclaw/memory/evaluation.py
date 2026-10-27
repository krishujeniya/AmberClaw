"""Evaluation metrics and benchmarking suite for AmberClaw RAG.

Implements Information Retrieval (IR) and Generation metrics:
- Precision@K, Recall@K
- Mean Reciprocal Rank (MRR@K)
- Normalized Discounted Cumulative Gain (nDCG@K)
- Faithfulness & Answer Relevancy
- Latency (p50/p95/p99) & Token Cost Tracking
"""

from __future__ import annotations

import math
import re
from typing import Any, ClassVar

from pydantic import BaseModel


# ==============================================================================
# 1. Ranking & Retrieval Metrics (IR)
# ==============================================================================
def compute_mrr_at_k(
    retrieved_ids: list[str],
    relevant_ids: set[str] | list[str],
    k: int = 10,
) -> float:
    """Compute Mean Reciprocal Rank at K (MRR@K).

    Returns 1 / rank of the first relevant document in top K, or 0.0 if none found.
    """
    rel_set = {str(r) for r in relevant_ids}
    if not rel_set or not retrieved_ids or k <= 0:
        return 0.0

    for rank, doc_id in enumerate(retrieved_ids[:k], start=1):
        if str(doc_id) in rel_set:
            return 1.0 / rank
    return 0.0


def compute_ndcg_at_k(
    retrieved_ids: list[str],
    relevance_scores: dict[str, float] | set[str] | list[str],
    k: int = 10,
) -> float:
    """Compute Normalized Discounted Cumulative Gain at K (nDCG@K).

    Args:
        retrieved_ids: Ordered list of retrieved document IDs.
        relevance_scores: Dict mapping doc_id -> relevance grade, or set/list of relevant IDs (grade=1.0).
        k: Cutoff rank (default 10).

    Returns:
        float: Normalized DCG score between 0.0 and 1.0.
    """
    if not retrieved_ids or not relevance_scores or k <= 0:
        return 0.0

    # Normalize relevance mapping
    rel_map: dict[str, float] = {}
    if isinstance(relevance_scores, dict):
        rel_map = {str(k_id): float(v) for k_id, v in relevance_scores.items()}
    else:
        rel_map = {str(item): 1.0 for item in relevance_scores}

    # Calculate DCG@K
    dcg = 0.0
    for idx, doc_id in enumerate(retrieved_ids[:k]):
        rel = rel_map.get(str(doc_id), 0.0)
        if rel > 0:
            dcg += (2.0**rel - 1.0) / math.log2(idx + 2.0)

    # Calculate Ideal DCG@K (IDCG@K)
    sorted_rels = sorted(rel_map.values(), reverse=True)[:k]
    idcg = 0.0
    for idx, rel in enumerate(sorted_rels):
        if rel > 0:
            idcg += (2.0**rel - 1.0) / math.log2(idx + 2.0)

    if idcg == 0.0:
        return 0.0
    return min(1.0, dcg / idcg)


def compute_precision_at_k(
    retrieved_ids: list[str],
    relevant_ids: set[str] | list[str],
    k: int = 10,
) -> float:
    """Compute Precision at K.

    Precision@K = (Relevant documents in top K) / K.
    """
    rel_set = {str(r) for r in relevant_ids}
    if not retrieved_ids or k <= 0:
        return 0.0

    top_k = retrieved_ids[:k]
    hits = sum(1 for doc_id in top_k if str(doc_id) in rel_set)
    return hits / float(min(k, len(top_k))) if top_k else 0.0


def compute_recall_at_k(
    retrieved_ids: list[str],
    relevant_ids: set[str] | list[str],
    k: int = 10,
) -> float:
    """Compute Recall at K.

    Recall@K = (Relevant documents in top K) / (Total relevant documents).
    """
    rel_set = {str(r) for r in relevant_ids}
    if not rel_set:
        return 1.0
    if not retrieved_ids or k <= 0:
        return 0.0

    top_k = retrieved_ids[:k]
    hits = sum(1 for doc_id in top_k if str(doc_id) in rel_set)
    return min(1.0, hits / float(len(rel_set)))


# ==============================================================================
# 2. Generation & Faithfulness Metrics
# ==============================================================================
def compute_faithfulness(answer: str, contexts: list[str]) -> float:
    """Evaluate factual faithfulness of generated answer against retrieved contexts.

    Computes token-level and statement grounding ratio.
    """
    if not answer or not contexts:
        return 0.0

    # Tokenize meaningful words (>3 chars)
    def _words(text: str) -> set[str]:
        return {w.lower() for w in re.findall(r"\b\w{4,}\b", text)}

    answer_words = _words(answer)
    if not answer_words:
        return 1.0

    context_words: set[str] = set()
    for ctx in contexts:
        context_words |= _words(ctx)

    if not context_words:
        return 0.0

    grounded_words = answer_words.intersection(context_words)
    return min(1.0, len(grounded_words) / float(len(answer_words)))


def compute_answer_relevancy(answer: str, question: str) -> float:
    """Evaluate lexical/semantic relevancy of answer to the query."""
    if not answer or not question:
        return 0.0

    def _words(text: str) -> set[str]:
        return {w.lower() for w in re.findall(r"\b\w{3,}\b", text)}

    q_words = _words(question)
    a_words = _words(answer)
    if not q_words:
        return 1.0

    overlap = q_words.intersection(a_words)
    return min(1.0, len(overlap) / float(len(q_words)))


# ==============================================================================
# 3. Latency & Cost Tracking
# ==============================================================================
class QueryLatency(BaseModel):
    """Detailed query timing profile in milliseconds."""

    bm25_ms: float = 0.0
    vector_ms: float = 0.0
    rerank_ms: float = 0.0
    total_ms: float = 0.0


class CostProfile(BaseModel):
    """Estimated query cost based on token consumption."""

    embedding_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0


class RAGMetricsTracker:
    """Tracks latency percentiles (p50/p95/p99) and token costs across queries."""

    # Default pricing per 1M tokens (USD)
    DEFAULT_PRICING: ClassVar[dict[str, float]] = {
        "text-embedding-3-small": 0.02,
        "text-embedding-3-large": 0.13,
        "gpt-4o-mini-prompt": 0.15,
        "gpt-4o-mini-completion": 0.60,
    }

    def __init__(self, embedding_model: str = "text-embedding-3-small"):
        self.embedding_model = embedding_model
        self.latencies: list[QueryLatency] = []
        self.costs: list[CostProfile] = []

    def record_query(
        self,
        latency: QueryLatency,
        embedding_tokens: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> CostProfile:
        """Record query latency and token consumption."""
        self.latencies.append(latency)

        embed_price_per_m = self.DEFAULT_PRICING.get(self.embedding_model, 0.02)
        prompt_price_per_m = self.DEFAULT_PRICING["gpt-4o-mini-prompt"]
        comp_price_per_m = self.DEFAULT_PRICING["gpt-4o-mini-completion"]

        cost = (
            (embedding_tokens / 1_000_000.0) * embed_price_per_m
            + (prompt_tokens / 1_000_000.0) * prompt_price_per_m
            + (completion_tokens / 1_000_000.0) * comp_price_per_m
        )

        cost_entry = CostProfile(
            embedding_tokens=embedding_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost_usd=round(cost, 6),
        )
        self.costs.append(cost_entry)
        return cost_entry

    def get_latency_summary(self) -> dict[str, dict[str, float]]:
        """Calculate p50, p95, p99, and mean for each latency phase."""
        if not self.latencies:
            empty = {"p50": 0.0, "p95": 0.0, "p99": 0.0, "mean": 0.0}
            return {
                "bm25_ms": empty,
                "vector_ms": empty,
                "rerank_ms": empty,
                "total_ms": empty,
            }

        def _stats(values: list[float]) -> dict[str, float]:
            sorted_v = sorted(values)
            n = len(sorted_v)
            return {
                "p50": round(sorted_v[int(n * 0.50)], 3),
                "p95": round(sorted_v[min(int(n * 0.95), n - 1)], 3),
                "p99": round(sorted_v[min(int(n * 0.99), n - 1)], 3),
                "mean": round(sum(sorted_v) / n, 3),
            }

        return {
            "bm25_ms": _stats([item.bm25_ms for item in self.latencies]),
            "vector_ms": _stats([item.vector_ms for item in self.latencies]),
            "rerank_ms": _stats([item.rerank_ms for item in self.latencies]),
            "total_ms": _stats([item.total_ms for item in self.latencies]),
        }

    def get_cost_summary(self) -> dict[str, Any]:
        """Aggregate total tokens and estimated spend."""
        total_embed = sum(c.embedding_tokens for c in self.costs)
        total_prompt = sum(c.prompt_tokens for c in self.costs)
        total_comp = sum(c.completion_tokens for c in self.costs)
        total_usd = sum(c.estimated_cost_usd for c in self.costs)

        return {
            "total_queries": len(self.costs),
            "total_embedding_tokens": total_embed,
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_comp,
            "total_estimated_cost_usd": round(total_usd, 6),
            "avg_cost_per_query_usd": (
                round(total_usd / len(self.costs), 6) if self.costs else 0.0
            ),
        }
