# ruff: noqa: PLR2004
"""Unit tests for Section 2 Memory & RAG Benchmarking Suite.

Covers:
- IR metrics: MRR@10, nDCG@10, Precision@10, Recall@10 [Line 189]
- Faithfulness and Relevancy evaluations [Line 189]
- Document-type chunking benchmarks [Line 190]
- Latency (p50/p95/p99) and token cost tracking [Line 191]
"""

from amberclaw.memory.evaluation import (
    QueryLatency,
    RAGMetricsTracker,
    compute_answer_relevancy,
    compute_faithfulness,
    compute_mrr_at_k,
    compute_ndcg_at_k,
    compute_precision_at_k,
    compute_recall_at_k,
)
from amberclaw.memory.rag_pipeline import HybridRetriever
from benchmarks.chunking_benchmark import (
    benchmark_document_type,
    run_chunking_benchmarks,
)


# ==============================================================================
# Line 189: Information Retrieval Ranking Metrics (MRR@10, nDCG@10, P@K, R@K)
# ==============================================================================
def test_compute_mrr_at_k():
    """Verify Mean Reciprocal Rank (MRR) at K."""
    relevant = {"doc_gold"}

    # Rank 1 hit -> MRR = 1.0
    assert compute_mrr_at_k(["doc_gold", "doc_2", "doc_3"], relevant, k=10) == 1.0

    # Rank 2 hit -> MRR = 0.5
    assert compute_mrr_at_k(["doc_1", "doc_gold", "doc_3"], relevant, k=10) == 0.5

    # Rank 3 hit -> MRR = 1/3 = 0.3333...
    assert (
        round(compute_mrr_at_k(["doc_1", "doc_2", "doc_gold"], relevant, k=10), 3)
        == 0.333
    )

    # Rank beyond K -> MRR = 0.0
    assert compute_mrr_at_k(["doc_1", "doc_2", "doc_gold"], relevant, k=2) == 0.0

    # Not found -> MRR = 0.0
    assert compute_mrr_at_k(["doc_1", "doc_2", "doc_3"], relevant, k=10) == 0.0


def test_compute_ndcg_at_k():
    """Verify Normalized Discounted Cumulative Gain (nDCG) at K."""
    relevance_scores = {"doc_a": 3.0, "doc_b": 2.0, "doc_c": 1.0}

    # Perfect ranking: [doc_a, doc_b, doc_c] -> nDCG = 1.0
    perfect_ndcg = compute_ndcg_at_k(["doc_a", "doc_b", "doc_c"], relevance_scores, k=3)
    assert round(perfect_ndcg, 4) == 1.0

    # Suboptimal ranking: [doc_c, doc_b, doc_a] -> nDCG < 1.0
    suboptimal_ndcg = compute_ndcg_at_k(
        ["doc_c", "doc_b", "doc_a"], relevance_scores, k=3
    )
    assert 0.0 < suboptimal_ndcg < 1.0

    # Empty retrieved or empty relevance
    assert compute_ndcg_at_k([], relevance_scores, k=3) == 0.0
    assert compute_ndcg_at_k(["doc_a"], {}, k=3) == 0.0


def test_compute_precision_and_recall_at_k():
    """Verify Precision@K and Recall@K."""
    relevant = {"doc_1", "doc_2"}
    retrieved = ["doc_1", "doc_x", "doc_2", "doc_y", "doc_z"]

    # Precision@2: 1 relevant out of 2 = 0.5
    assert compute_precision_at_k(retrieved, relevant, k=2) == 0.5

    # Precision@3: 2 relevant out of 3 = 2/3 = 0.6667
    assert round(compute_precision_at_k(retrieved, relevant, k=3), 3) == 0.667

    # Recall@2: 1 relevant retrieved out of 2 total relevant = 0.5
    assert compute_recall_at_k(retrieved, relevant, k=2) == 0.5

    # Recall@3: 2 relevant retrieved out of 2 total relevant = 1.0
    assert compute_recall_at_k(retrieved, relevant, k=3) == 1.0


def test_compute_faithfulness_and_relevancy():
    """Verify factual faithfulness and question relevancy calculations."""
    context = ["AmberClaw is an AI operating system kernel with zero-trust isolation."]

    # Fully faithful answer
    faithful_answer = "AmberClaw is an operating system with zero-trust isolation."
    assert compute_faithfulness(faithful_answer, context) > 0.8

    # Unfaithful answer
    unfaithful_answer = (
        "AmberClaw is an electronic musical instrument produced in Japan."
    )
    assert compute_faithfulness(unfaithful_answer, context) < 0.2

    # Relevancy
    question = "What is AmberClaw?"
    assert compute_answer_relevancy(faithful_answer, question) > 0.0


# ==============================================================================
# Line 190: Chunking Benchmarks by Document Type
# ==============================================================================
def test_chunking_benchmark_document_types():
    """Verify chunking benchmarks execute across Markdown, Python, Text, and HTML."""
    md_result = benchmark_document_type("markdown", "# Header\nContent paragraph here.")
    assert md_result["chunk_count"] >= 1
    assert md_result["payload_kb"] > 0
    assert md_result["throughput_kb_s"] >= 0

    py_result = benchmark_document_type("python", "def test_func():\n    return 42\n")
    assert py_result["chunk_count"] >= 1

    html_result = benchmark_document_type(
        "html", "<html><body><p>Hello HTML</p></body></html>"
    )
    assert html_result["chunk_count"] >= 1


def test_run_chunking_benchmarks_export(tmp_path):
    """Verify full chunking benchmark suite exports JSON report."""
    out_file = tmp_path / "chunk_results.json"
    results = run_chunking_benchmarks(output_file=out_file)

    assert "markdown" in results
    assert "python_code" in results
    assert "plain_text" in results
    assert "html" in results
    assert out_file.exists()


# ==============================================================================
# Line 191: Latency (p50/p95/p99) and Cost Metrics Tracking
# ==============================================================================
def test_rag_metrics_tracker_latency_and_costs():
    """Verify latency percentiles and token cost aggregation."""
    tracker = RAGMetricsTracker(embedding_model="text-embedding-3-small")

    # Record multiple query timings
    tracker.record_query(
        QueryLatency(bm25_ms=2.0, vector_ms=10.0, rerank_ms=5.0, total_ms=17.0),
        embedding_tokens=20,
        prompt_tokens=200,
        completion_tokens=50,
    )
    tracker.record_query(
        QueryLatency(bm25_ms=4.0, vector_ms=14.0, rerank_ms=7.0, total_ms=25.0),
        embedding_tokens=30,
        prompt_tokens=250,
        completion_tokens=60,
    )

    # Check latency percentiles
    lat_summary = tracker.get_latency_summary()
    assert lat_summary["total_ms"]["p50"] in [17.0, 25.0]
    assert lat_summary["total_ms"]["mean"] == 21.0

    # Check cost summary
    cost_summary = tracker.get_cost_summary()
    assert cost_summary["total_queries"] == 2
    assert cost_summary["total_embedding_tokens"] == 50
    assert cost_summary["total_prompt_tokens"] == 450
    assert cost_summary["total_completion_tokens"] == 110
    assert cost_summary["total_estimated_cost_usd"] > 0.0


def test_hybrid_retriever_query_latency_profiling(tmp_path):
    """Verify HybridRetriever.retrieve records execution latency."""
    retriever = HybridRetriever(db_dir=tmp_path, collection_name="latency_test")
    retriever.retrieve("sample query")

    assert "total_ms" in retriever.last_query_metrics
    assert retriever.last_query_metrics["total_ms"] >= 0.0
