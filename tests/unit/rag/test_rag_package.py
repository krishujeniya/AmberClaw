# ruff: noqa: PLR2004
"""Unit tests for the amberclaw.rag package (chunking, embeddings, indexing, retrieval, knowledge base)."""

import pytest

from amberclaw.rag.chunker import TextChunker
from amberclaw.rag.embedder import DeterministicHashEmbedder, cosine_similarity
from amberclaw.rag.indexer import DocumentIndex
from amberclaw.rag.knowledge_base import KnowledgeBase
from amberclaw.rag.retriever import DocumentRetriever

# ==============================================================================
# Chunker Tests
# ==============================================================================


def test_text_chunker_basic():
    text = (
        "AmberClaw is an enterprise sovereign agent operating system.\n\n"
        "It provides zero-trust security, human-in-the-loop approvals, and full audit logs.\n\n"
        "Subagents run in sandboxed processes with hardware-accelerated memory boundaries."
    )
    chunker = TextChunker(chunk_size=100, chunk_overlap=20)
    chunks = chunker.chunk_text(text, metadata={"source": "overview.md"})

    assert len(chunks) >= 2
    for c in chunks:
        assert len(c.text) > 0
        assert c.metadata["source"] == "overview.md"
        assert c.start_char >= 0
        assert c.end_char > c.start_char


def test_text_chunker_validation():
    with pytest.raises(ValueError, match="chunk_size must be positive"):
        TextChunker(chunk_size=0)

    with pytest.raises(
        ValueError, match="chunk_overlap must be strictly less than chunk_size"
    ):
        TextChunker(chunk_size=100, chunk_overlap=100)

    with pytest.raises(ValueError, match="chunk_overlap cannot be negative"):
        TextChunker(chunk_size=100, chunk_overlap=-5)


def test_chunk_documents():
    chunker = TextChunker(chunk_size=80, chunk_overlap=10)
    docs = [
        {
            "content": "Document 1 content about machine learning and inference engines.",
            "id": "doc1",
        },
        {
            "content": "Document 2 content detailing governance policies and compliance packs.",
            "id": "doc2",
        },
    ]
    chunks = chunker.chunk_documents(docs)
    assert len(chunks) >= 2
    assert any(c.metadata.get("id") == "doc1" for c in chunks)
    assert any(c.metadata.get("id") == "doc2" for c in chunks)


# ==============================================================================
# Embedder Tests
# ==============================================================================


def test_hash_embedder_and_cosine():
    embedder = DeterministicHashEmbedder(dimensions=32)

    vec_a = embedder.embed_text("Deep reinforcement learning for autonomous agents")
    vec_b = embedder.embed_text(
        "Autonomous agents using reinforcement learning algorithms"
    )
    vec_c = embedder.embed_text(
        "French vanilla ice cream recipe with fresh strawberries"
    )

    assert len(vec_a) == 32
    sim_similar = cosine_similarity(vec_a, vec_b)
    sim_dissimilar = cosine_similarity(vec_a, vec_c)

    assert sim_similar > sim_dissimilar
    assert cosine_similarity(vec_a, vec_a) == pytest.approx(1.0, rel=1e-3)


def test_embedder_batch():
    embedder = DeterministicHashEmbedder(dimensions=16)
    batch = ["first query", "second prompt", "third response"]
    embeddings = embedder.embed_batch(batch)

    assert len(embeddings) == 3
    for emb in embeddings:
        assert len(emb) == 16


# ==============================================================================
# DocumentIndex & Retriever Tests
# ==============================================================================


def test_document_index_hybrid():
    index = DocumentIndex()
    embedder = DeterministicHashEmbedder(dimensions=32)
    chunker = TextChunker(chunk_size=120, chunk_overlap=20)

    t1 = "Kubernetes orchestration handles container deployments, pod restarts, and horizontal auto-scaling."
    t2 = "PostgreSQL relational databases support ACID transactions, WAL logging, and JSONB queries."

    c1 = chunker.chunk_text(t1, metadata={"topic": "k8s"})[0]
    c2 = chunker.chunk_text(t2, metadata={"topic": "postgres"})[0]

    emb1 = embedder.embed_text(c1.text)
    emb2 = embedder.embed_text(c2.text)

    index.add_chunk(c1, emb1)
    index.add_chunk(c2, emb2)
    assert index.total_chunks == 2

    # Vector search
    q_vec = embedder.embed_text("container scaling and pods")
    v_results = index.search_vector(q_vec, top_k=1)
    assert len(v_results) == 1
    assert v_results[0][0].metadata["topic"] == "k8s"

    # Keyword search
    k_results = index.search_keyword("PostgreSQL transactions", top_k=1)
    assert len(k_results) == 1
    assert k_results[0][0].metadata["topic"] == "postgres"


def test_retriever_hybrid_rrf():
    index = DocumentIndex()
    embedder = DeterministicHashEmbedder(dimensions=32)
    retriever = DocumentRetriever(index=index, embedder=embedder)

    chunker = TextChunker(chunk_size=150, chunk_overlap=30)
    text = (
        "The HIPAA compliance pack enforces encryption at rest using AES-256 and strict audit logging. "
        "The SOC2 pack ensures least-privilege IAM controls."
    )
    chunks = chunker.chunk_text(text)
    for c in chunks:
        index.add_chunk(c, embedder.embed_text(c.text))

    results = retriever.retrieve_hybrid("HIPAA compliance encryption", top_k=2)
    assert len(results) > 0
    assert results[0].retrieval_method == "hybrid_rrf"


# ==============================================================================
# KnowledgeBase Tests
# ==============================================================================


def test_knowledge_base_workflow():
    kb = KnowledgeBase(chunk_size=150, chunk_overlap=25)

    kb.add_document(
        doc_id="sec-01",
        text="All API endpoints require Bearer JWT authentication signed with ES256 keys.",
    )
    kb.add_document(
        doc_id="net-02",
        text="WebSocket streams multiplex token frames, progress frames, and terminal signal frames.",
    )

    assert kb.document_count == 2
    assert kb.chunk_count >= 2

    res = kb.query("Bearer JWT authentication", top_k=1)
    assert len(res) == 1
    assert res[0].chunk.metadata["doc_id"] == "sec-01"

    context_block = kb.build_context_block("Bearer JWT authentication")
    assert "### Grounded Knowledge Base Context:" in context_block
    assert "Doc: sec-01" in context_block

    kb.clear()
    assert kb.document_count == 0
    assert kb.chunk_count == 0
