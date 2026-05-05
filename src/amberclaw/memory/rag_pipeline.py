"""RAG Pipeline for AmberClaw.

Implements Document Ingestion (multi-format) and Hybrid Retrieval
(Vector + BM25 + Cross-Encoder Reranking).
"""

from pathlib import Path
from typing import List, Any

from loguru import logger

try:
    from langchain_core.documents import Document
    from langchain_community.document_loaders import UnstructuredFileLoader, DirectoryLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_community.retrievers import BM25Retriever
    from langchain_chroma import Chroma
    from langchain_openai import OpenAIEmbeddings
    from langchain.retrievers import ContextualCompressionRetriever
    from langchain.retrievers.document_compressors import CrossEncoderReranker
    from langchain_community.cross_encoders import HuggingFaceCrossEncoder
    from langchain.retrievers.ensemble import EnsembleRetriever
except ImportError as e:
    logger.warning(f"RAG dependencies missing. Install with `pip install amberclaw[docs,vectordb]`. {e}")
    Document = None  # type: ignore


class DocumentIngestor:
    """Ingests multi-format documents from a directory or file."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def load_and_split(self, path: Path) -> List["Document"]:
        if Document is None:
            raise ImportError("LangChain not installed")

        if path.is_file():
            file_loader = UnstructuredFileLoader(str(path))
            docs = file_loader.load()
        elif path.is_dir():
            dir_loader = DirectoryLoader(str(path), use_multithreading=True)
            docs = dir_loader.load()
        else:
            raise ValueError(f"Path {path} is not a valid file or directory.")

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )
        return splitter.split_documents(docs)


class HybridRetriever:
    """Hybrid Retriever combining Dense Vector, BM25, and Cross-Encoder."""

    def __init__(self, db_dir: Path, collection_name: str = "amberclaw_docs"):
        if Document is None:
            raise ImportError("LangChain not installed")

        self.db_dir = db_dir
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self.embeddings = OpenAIEmbeddings()

        self.vector_store = Chroma(
            collection_name=self.collection_name,
            persist_directory=str(self.db_dir),
            embedding_function=self.embeddings
        )

        # Local BM25 index might need separate persistence, simplified here for demo
        from typing import Any
        self.bm25_retriever: Any = None

    def ingest(self, docs: List["Document"]) -> None:
        """Add documents to the retriever."""
        if not docs:
            return

        # Add to vector store
        self.vector_store.add_documents(docs)

        # Re-initialize BM25
        self.bm25_retriever = BM25Retriever.from_documents(docs)
        self.bm25_retriever.k = 5
        logger.info(f"Ingested {len(docs)} document chunks.")

    def get_retriever(self, top_k: int = 5) -> "Any":
        """Build and return the hybrid contextual compression retriever."""
        if not self.bm25_retriever:
            logger.warning("BM25 index not initialized. Falling back to Vector-only.")
            base_retriever = self.vector_store.as_retriever(search_kwargs={"k": top_k * 2})
        else:
            vector_retriever = self.vector_store.as_retriever(search_kwargs={"k": top_k * 2})
            base_retriever = EnsembleRetriever(
                retrievers=[self.bm25_retriever, vector_retriever],
                weights=[0.3, 0.7]
            )

        try:
            model = HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-base")
            compressor = CrossEncoderReranker(model=model, top_n=top_k)
            return ContextualCompressionRetriever(
                base_compressor=compressor,
                base_retriever=base_retriever
            )
        except Exception as e:
            logger.error(f"Failed to load reranker: {e}. Falling back to base retriever.")
            return base_retriever
