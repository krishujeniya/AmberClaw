# ruff: noqa: E402, PLR2004
"""Unit tests for the RAG pipeline and hybrid retriever persistence."""

import sys
from unittest.mock import MagicMock, patch

# Force re-importing of memory modules to apply mocks correctly
for m in list(sys.modules.keys()):
    if "amberclaw.memory" in m:
        sys.modules.pop(m, None)



# Define a Document stub class
class DocumentStub:
    def __init__(self, page_content: str, metadata: dict | None = None):
        self.page_content = page_content
        self.metadata = metadata or {}


# Set up mock modules to satisfy imports if langchain is not installed
mock_modules = [
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
]

for mod in mock_modules:
    sys.modules[mod] = MagicMock()

# Bind stubs to mock modules
sys.modules["langchain_core.documents"].Document = DocumentStub

# Stub out load classes
mock_unstructured_loader = MagicMock()
sys.modules["langchain_community.document_loaders"].UnstructuredFileLoader = mock_unstructured_loader

mock_recursive_splitter = MagicMock()
sys.modules["langchain_text_splitters"].RecursiveCharacterTextSplitter = mock_recursive_splitter


# Picklable fake class to replace BM25Retriever
class FakeBM25Retriever:
    def __init__(self, docs=None):
        self.docs = docs or []
        self.k = 5

    @classmethod
    def from_documents(cls, docs):
        return cls(docs)

sys.modules["langchain_community.retrievers"].BM25Retriever = FakeBM25Retriever


# Now import the target classes
from amberclaw.memory.rag_pipeline import DocumentIngestor, HybridRetriever


def test_document_ingestor_split(tmp_path):
    ingestor = DocumentIngestor(chunk_size=100, chunk_overlap=10)
    
    loader_instance = MagicMock()
    loader_instance.load.return_value = [DocumentStub(page_content="Hello world this is a test document to split.")]
    mock_unstructured_loader.return_value = loader_instance
    
    splitter_instance = MagicMock()
    splitter_instance.split_documents.return_value = [
        DocumentStub(page_content="Hello world"),
        DocumentStub(page_content="this is a test"),
    ]
    mock_recursive_splitter.return_value = splitter_instance
    
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("Hello world")
    
    docs = ingestor.load_and_split(test_file)
    assert len(docs) == 2
    assert docs[0].page_content == "Hello world"


def test_hybrid_retriever_persistence(tmp_path):
    # Scenario 1: Initial ingest
    retriever = HybridRetriever(db_dir=tmp_path, collection_name="test_collection")
    
    doc1 = DocumentStub(page_content="AmberClaw is an AI OS kernel.", metadata={"source": "doc1"})
    doc2 = DocumentStub(page_content="It supports zero-trust security.", metadata={"source": "doc2"})
    
    retriever.ingest([doc1, doc2])
    
    # Check that documents are written to disk
    assert retriever.docs_path.exists()
    assert retriever.bm25_path.exists()

    # Scenario 2: Load from disk on new instance
    retriever_new = HybridRetriever(db_dir=tmp_path, collection_name="test_collection")
    
    assert len(retriever_new.bm25_docs) == 2
    assert retriever_new.bm25_docs[0].page_content == "AmberClaw is an AI OS kernel."
    assert retriever_new.bm25_retriever is not None
    
    # Scenario 3: Ingesting more documents merges correctly
    doc3 = DocumentStub(page_content="It also supports hybrid RAG pipelines.", metadata={"source": "doc3"})
    retriever_new.ingest([doc3])
    
    assert len(retriever_new.bm25_docs) == 3
    assert retriever_new.bm25_docs[2].page_content == "It also supports hybrid RAG pipelines."


def test_hybrid_retriever_get_retriever(tmp_path):
    retriever = HybridRetriever(db_dir=tmp_path, collection_name="test_collection")
    doc = DocumentStub(page_content="Sample text.")
    retriever.ingest([doc])
    
    r = retriever.get_retriever(top_k=3)
    assert r is not None


@patch("httpx.get")
def test_document_ingestor_url(mock_get):
    mock_resp = MagicMock()
    mock_resp.text = "<html><head><title>Ignore Title</title><style>body {color: blue;}</style></head><body><h1>Title Here</h1><p>Paragraph text</p></body></html>"
    mock_resp.status_code = 200
    mock_get.return_value = mock_resp

    mock_recursive_splitter.return_value.split_documents.side_effect = lambda docs: docs

    ingestor = DocumentIngestor()
    docs = ingestor.load_url("https://example.com/test-url")
    assert len(docs) == 1
    # Check HTML stripping and tag extraction
    content = docs[0].page_content
    assert "Title Here" in content
    assert "Paragraph text" in content
    assert "Ignore Title" not in content
    assert "color: blue" not in content
    assert docs[0].metadata["source"] == "https://example.com/test-url"


def test_document_ingestor_text():
    mock_recursive_splitter.return_value.split_documents.side_effect = lambda docs: docs

    ingestor = DocumentIngestor()
    docs = ingestor.load_text("Hello from a chat message", source="discord")
    assert len(docs) == 1
    assert docs[0].page_content == "Hello from a chat message"
    assert docs[0].metadata["source"] == "discord"


def test_document_ingestor_file_fallback(tmp_path):
    mock_recursive_splitter.return_value.split_documents.side_effect = lambda docs: docs

    # Write a test file
    test_file = tmp_path / "fallback_file.md"
    test_file.write_text("# Read Me\nThis is standard text content.", encoding="utf-8")

    # Force UnstructuredFileLoader to raise an error to trigger the fallback reader
    mock_unstructured_loader.side_effect = Exception("Failed loading unstructured")

    ingestor = DocumentIngestor()
    docs = ingestor.load_file(test_file)
    assert len(docs) == 1
    assert "# Read Me" in docs[0].page_content
    assert docs[0].metadata["source"] == str(test_file)

    # Restore side_effect to avoid affecting other tests
    mock_unstructured_loader.side_effect = None


def test_document_ingestor_unified_ingest(tmp_path):
    # Set up mock retriever and ingestor
    ingestor = DocumentIngestor(workspace=tmp_path)
    ingestor.retriever = MagicMock()

    mock_recursive_splitter.return_value.split_documents.side_effect = lambda docs: docs

    # Test ingesting URL
    with patch("httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.text = "<html><body><p>URL Webpage Content</p></body></html>"
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        count = ingestor.ingest("https://example.com/dynamic-page")
        assert count == 1
        assert ingestor.retriever.ingest.call_count == 1
        ingestor.retriever.ingest.reset_mock()

    # Test ingesting file
    test_file = tmp_path / "direct_file.txt"
    test_file.write_text("Direct file content")
    count = ingestor.ingest(test_file)
    assert count == 1
    assert ingestor.retriever.ingest.call_count == 1
    ingestor.retriever.ingest.reset_mock()

    # Test ingesting message string
    count = ingestor.ingest("Direct message text content", metadata={"session_id": "test_sess"})
    assert count == 1
    assert ingestor.retriever.ingest.call_count == 1
    ingestor.retriever.ingest.reset_mock()

