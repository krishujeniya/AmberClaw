# ruff: noqa: E402, PLR2004
"""Unit tests for incremental BM25 indexing, deduplication, and persistence in HybridRetriever."""

import sys
from unittest.mock import MagicMock

# Reset memory modules to apply mocks cleanly
for m in list(sys.modules.keys()):
    if "amberclaw.memory" in m:
        sys.modules.pop(m, None)


class DocumentStub:
    def __init__(self, page_content: str, metadata: dict | None = None):
        self.page_content = page_content
        self.metadata = metadata or {}


# Set up mock modules
for mod in [
    "langchain.retrievers",
    "langchain.retrievers.document_compressors",
    "langchain.retrievers.ensemble",
    "langchain_chroma",
    "langchain_community.cross_encoders",
    "langchain_community.document_loaders",
    "langchain_community.retrievers",
    "langchain_core.documents",
    "langchain_openai",
    "langchain_text_splitters",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

sys.modules["langchain_core.documents"].Document = DocumentStub


class FakeBM25Retriever:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.k = 5

    @classmethod
    def from_documents(cls, docs):
        return cls(docs)

    def add_documents(self, docs):
        self.docs.extend(docs)


sys.modules["langchain_community.retrievers"].BM25Retriever = FakeBM25Retriever

from amberclaw.memory.rag_pipeline import HybridRetriever


def test_incremental_bm25_deduplication(tmp_path):
    """Test that ingesting the exact same documents twice deduplicates and avoids redundant indexing."""
    retriever = HybridRetriever(db_dir=tmp_path, collection_name="test_inc")

    doc1 = DocumentStub("System kernel architecture", {"id": "1"})
    doc2 = DocumentStub("Zero-trust sandboxing engine", {"id": "2"})

    # First ingestion
    added_count = retriever.ingest([doc1, doc2])
    assert added_count == 2
    assert len(retriever.bm25_docs) == 2

    # Second ingestion of duplicate documents
    added_count_2 = retriever.ingest([doc1, doc2])
    assert added_count_2 == 0
    assert len(retriever.bm25_docs) == 2

    # Ingesting a third new document
    doc3 = DocumentStub("Hardware enclave memory isolation", {"id": "3"})
    added_count_3 = retriever.ingest([doc3])
    assert added_count_3 == 1
    assert len(retriever.bm25_docs) == 3


def test_incremental_bm25_persistence_reload(tmp_path):
    """Test that incremental documents persist to disk and reload with hashes intact."""
    retriever = HybridRetriever(db_dir=tmp_path, collection_name="test_inc")
    doc1 = DocumentStub("Document alpha", {"source": "alpha"})
    retriever.ingest([doc1])

    # Re-instantiate from same directory
    retriever2 = HybridRetriever(db_dir=tmp_path, collection_name="test_inc")
    assert len(retriever2.bm25_docs) == 1
    assert len(retriever2._doc_hashes) == 1

    # Ingesting doc1 into reloaded retriever should be skipped as duplicate
    added = retriever2.ingest([doc1])
    assert added == 0

    # Ingesting doc2 should succeed
    doc2 = DocumentStub("Document beta", {"source": "beta"})
    added = retriever2.ingest([doc2])
    assert added == 1
    assert len(retriever2.bm25_docs) == 2
