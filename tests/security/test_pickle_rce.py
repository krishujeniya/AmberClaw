import os
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from amberclaw.data.tools.data_loader import ALLOW_UNSAFE_PICKLE_ENV_VAR, load_pickle
from amberclaw.memory.rag_pipeline import Document, HybridRetriever



def test_data_loader_pickle_blocked_by_default(tmp_path: Path):
    """Verify that pickle loading in data_loader is blocked when env var is not set."""
    if ALLOW_UNSAFE_PICKLE_ENV_VAR in os.environ:
        del os.environ[ALLOW_UNSAFE_PICKLE_ENV_VAR]

    dummy_file = tmp_path / "test.pkl"
    dummy_file.write_bytes(b"dummy")

    with pytest.raises(ValueError, match="Pickle loading is disabled by default"):
        load_pickle(str(dummy_file))


def test_rag_pipeline_json_persistence(tmp_path: Path):
    """Verify that HybridRetriever persists and loads documents using JSON format without pickle."""
    retriever = HybridRetriever(db_dir=tmp_path, collection_name="test_json_collection")
    doc1 = Document(page_content="Security test doc 1", metadata={"source": "test1"})
    doc2 = Document(page_content="Security test doc 2", metadata={"source": "test2"})

    retriever.ingest([doc1, doc2])

    assert retriever.docs_path.exists()
    assert retriever.docs_path.suffix == ".json"

    # Verify content is valid JSON
    data = json.loads(retriever.docs_path.read_text(encoding="utf-8"))
    assert len(data) == 2
    assert data[0]["page_content"] == "Security test doc 1"

    # Reload in new instance
    new_retriever = HybridRetriever(db_dir=tmp_path, collection_name="test_json_collection")
    assert len(new_retriever.bm25_docs) == 2
    assert new_retriever.bm25_docs[0].page_content == "Security test doc 1"
