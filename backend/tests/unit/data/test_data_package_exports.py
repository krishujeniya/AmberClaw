"""Tests for the data-science package surface and RAG entry points.

These cover the final DEBT-12 close-out: every module under
``amberclaw.data`` must expose real, importable behavior instead of a
``PLANNED — NOT IMPLEMENTED`` docstring.
"""

import pytest

import amberclaw.data.chunker as data_chunker
import amberclaw.data.embedder as data_embedder
import amberclaw.data.indexer as data_indexer
import amberclaw.data.knowledge_base as data_knowledge_base
import amberclaw.data.retriever as data_retriever
from amberclaw import rag
from amberclaw.data import tools, utils
from amberclaw.data.parsers import (
    PythonOutputParser,
    SQLOutputParser,
    extract_python_code,
    extract_sql_code,
)

EMBEDDING_DIMENSIONS = 16
EXPECTED_REVENUE_TOTAL = 35


def test_data_chunker_aliases_canonical_rag_types():
    assert data_chunker.Chunk is rag.Chunk
    assert data_chunker.TextChunker is rag.TextChunker

    chunks = data_chunker.TextChunker(chunk_size=40, chunk_overlap=5).chunk_text(
        "AmberClaw ingests documents and returns grounded, cited context."
    )
    assert chunks
    assert all(isinstance(chunk, rag.Chunk) for chunk in chunks)


def test_data_embedder_aliases_canonical_rag_types():
    assert data_embedder.BaseEmbedder is rag.BaseEmbedder
    assert data_embedder.DeterministicHashEmbedder is rag.DeterministicHashEmbedder
    assert data_embedder.EmbeddingResult is rag.EmbeddingResult
    assert data_embedder.cosine_similarity is rag.cosine_similarity

    embedder = data_embedder.DeterministicHashEmbedder(dimensions=EMBEDDING_DIMENSIONS)
    assert len(embedder.embed_text("revenue by region")) == EMBEDDING_DIMENSIONS
    assert data_embedder.cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_data_index_and_retriever_alias_canonical_rag_types():
    assert data_indexer.DocumentIndex is rag.DocumentIndex
    assert data_retriever.DocumentRetriever is rag.DocumentRetriever
    assert data_retriever.RetrievalResult is rag.RetrievalResult


def test_data_knowledge_base_supports_ingest_and_grounded_query():
    assert data_knowledge_base.KnowledgeBase is rag.KnowledgeBase

    kb = data_knowledge_base.KnowledgeBase(chunk_size=120, chunk_overlap=10)
    kb.add_documents(
        [
            {
                "id": "q3-report",
                "content": (
                    "Q3 revenue grew 18 percent. The west region led growth "
                    "with 24 percent expansion."
                ),
            },
            {
                "id": "q4-plan",
                "content": "The Q4 plan targets retention and margin expansion.",
            },
        ]
    )

    results = kb.query("which region grew fastest", top_k=2)
    assert results
    assert {res.chunk.metadata["doc_id"] for res in results} <= {
        "q3-report",
        "q4-plan",
    }

    context = kb.build_context_block("Q3 revenue growth", top_k=1)
    assert "Grounded Knowledge Base Context" in context
    assert "Doc:" in context


def test_parsers_package_exports_parse_fenced_code():
    assert PythonOutputParser().parse("```python\nx = 1\n```") == "x = 1"
    assert SQLOutputParser().parse("```sql\nSELECT 1;\n```") == "SELECT 1;"
    assert extract_python_code("no code here") is None
    assert extract_sql_code("```sql\nSELECT 2;\n```") == "SELECT 2;"


def test_tools_package_exports_are_lazy_and_functional(tmp_path):
    assert "load_csv" in tools.__all__
    assert "mlflow_ui_status" not in vars(tools)  # imported on first access only

    status = tools.mlflow_ui_status
    assert callable(status)
    # Resolved attributes are cached on the package for later lookups.
    assert tools.mlflow_ui_status is status
    assert "get_dataframe_summary" in dir(tools)

    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("region,revenue\nwest,24\neast,11\n", encoding="utf-8")
    frame = tools.load_csv(str(csv_path))
    assert list(frame.columns) == ["region", "revenue"]
    assert frame["revenue"].sum() == EXPECTED_REVENUE_TOTAL


def test_tools_package_rejects_unknown_attributes():
    with pytest.raises(AttributeError, match="not_a_real_tool"):
        _ = tools.not_a_real_tool


def test_utils_package_exports_helpers(tmp_path):
    assert "load_data" in utils.__all__
    assert "strip_markdown_code_fences" in dir(utils)
    assert "run_code_sandboxed_subprocess" not in vars(utils)

    csv_path = tmp_path / "metrics.csv"
    csv_path.write_text("metric,value\nlatency_ms,42\n", encoding="utf-8")
    frame = utils.load_data(str(csv_path))
    assert frame.to_dict("records") == [{"metric": "latency_ms", "value": 42}]

    assert utils.strip_markdown_code_fences("```python\nprint(1)\n```") == "print(1)"
    assert utils.format_agent_name("data_cleaning_agent") == (
        "---DATA CLEANING AGENT----"
    )


def test_utils_package_rejects_unknown_attributes():
    with pytest.raises(AttributeError, match="not_a_real_helper"):
        _ = utils.not_a_real_helper
