# ruff: noqa: S301, A002
"""RAG Pipeline for AmberClaw.

Implements Document Ingestion (multi-format) and Hybrid Retrieval
(Vector + BM25 + Cross-Encoder Reranking).
"""

import pickle
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

_RAG_ENABLED = True
try:
    from langchain.retrievers import ContextualCompressionRetriever
    from langchain.retrievers.document_compressors import CrossEncoderReranker
    from langchain.retrievers.ensemble import EnsembleRetriever
    from langchain_chroma import Chroma
    from langchain_community.cross_encoders import HuggingFaceCrossEncoder
    from langchain_community.document_loaders import (
        DirectoryLoader,
        UnstructuredFileLoader,
    )
    from langchain_community.retrievers import BM25Retriever
    from langchain_core.documents import Document
    from langchain_openai import OpenAIEmbeddings
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError as e:
    logger.warning(f"RAG dependencies missing. Install with `pip install amberclaw[docs,vectordb]`. {e}")
    _RAG_ENABLED = False
    DirectoryLoader = None  # type: ignore
    UnstructuredFileLoader = None  # type: ignore
    RecursiveCharacterTextSplitter = None  # type: ignore
    
    class Document:  # type: ignore
        """Fallback Document stub class when LangChain is not installed."""

        def __init__(self, page_content: str, metadata: dict[str, Any] | None = None):
            self.page_content = page_content
            self.metadata = metadata or {}


class HTMLToTextConverter(HTMLParser):
    """Cleanly converts HTML into readable text, discarding scripts, styles, and headers."""

    def __init__(self) -> None:
        super().__init__()
        self.result: list[str] = []
        self.ignore_tags = {"script", "style", "head", "title", "meta", "link"}
        self.ignore_depth = 0

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.ignore_tags:
            self.ignore_depth += 1
        elif tag in {"p", "h1", "h2", "h3", "h4", "h5", "h6", "div", "li", "tr", "br"}:
            self.result.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.ignore_tags:
            self.ignore_depth = max(0, self.ignore_depth - 1)
        elif tag in {"p", "h1", "h2", "h3", "h4", "h5", "h6", "div", "li", "tr"}:
            self.result.append("\n")

    def handle_data(self, data: str) -> None:
        if self.ignore_depth == 0:
            self.result.append(data)

    def get_text(self) -> str:
        raw_text = "".join(self.result)
        lines = []
        for raw_line in raw_text.splitlines():
            line = raw_line.strip()
            if line:
                lines.append(line)
        return "\n\n".join(lines)


class DocumentIngestor:
    """Ingests multi-format documents from files, URLs, and messages."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        workspace: Path | None = None,
        collection: str = "amberclaw_docs",
        embedding_model: str | None = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.workspace = workspace
        self.collection = collection
        self.embedding_model = embedding_model

        self.retriever = None
        if self.workspace:
            db_dir = self.workspace / "mem0_db"
            try:
                self.retriever = HybridRetriever(db_dir, collection_name=self.collection)
            except Exception as e:
                logger.warning(f"Could not initialize HybridRetriever for ingestion: {e}")

    def load_text(self, text: str, source: str = "message", metadata: dict[str, Any] | None = None) -> list["Document"]:
        """Wraps raw text content in a Document and splits it."""
        meta = {"source": source}
        if metadata:
            meta.update(metadata)

        doc = Document(page_content=text, metadata=meta)

        if RecursiveCharacterTextSplitter is not None:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )
            return splitter.split_documents([doc])
        return self._fallback_split(doc)

    def load_url(self, url: str, metadata: dict[str, Any] | None = None) -> list["Document"]:
        """Fetches a URL, converts HTML to clean text, and splits it."""
        try:
            response = httpx.get(url, follow_redirects=True, timeout=10.0)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch URL {url}: {e}")
            raise ValueError(f"Failed to fetch URL {url}: {e}") from e

        converter = HTMLToTextConverter()
        converter.feed(response.text)
        text = converter.get_text()

        meta = {"source": url, "url": url}
        if metadata:
            meta.update(metadata)

        return self.load_text(text, source=url, metadata=meta)

    def _load_single_file(self, path: Path, metadata: dict[str, Any] | None = None) -> list["Document"]:
        """Loads a single file using Unstructured, falling back to a plain UTF-8 text reader."""
        if UnstructuredFileLoader is not None:
            try:
                file_loader = UnstructuredFileLoader(str(path))
                return file_loader.load()
            except Exception as e:
                logger.debug(f"Unstructured loader failed: {e}. Falling back to plain text reader.")
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            meta = {"source": str(path)}
            if metadata:
                meta.update(metadata)
            return [Document(page_content=content, metadata=meta)]
        except Exception as ex:
            logger.error(f"Failed to read file {path} as text: {ex}")
            raise ValueError(f"Failed to read file {path}: {ex}") from ex

    def _load_directory(self, path: Path, metadata: dict[str, Any] | None = None) -> list["Document"]:
        """Loads a directory using DirectoryLoader, falling back to manual traversal."""
        if DirectoryLoader is not None:
            try:
                dir_loader = DirectoryLoader(str(path), use_multithreading=True)
                return dir_loader.load()
            except Exception as e:
                logger.debug(f"DirectoryLoader failed: {e}. Scanning files manually.")

        docs = []
        for file_path in path.rglob("*"):
            if file_path.is_file():
                try:
                    file_docs = self.load_file(file_path, metadata=metadata)
                    docs.extend(file_docs)
                except Exception as ex:
                    logger.debug(f"Skipping unreadable file {file_path}: {ex}")
                    continue
        return docs

    def load_file(self, path: Path, metadata: dict[str, Any] | None = None) -> list["Document"]:
        """Loads a file or directory. Falls back to direct text read if unstructured is missing."""
        path = Path(path)
        if path.is_file():
            docs = self._load_single_file(path, metadata=metadata)
        elif path.is_dir():
            docs = self._load_directory(path, metadata=metadata)
        else:
            raise ValueError(f"Path {path} is not a valid file or directory.")

        if RecursiveCharacterTextSplitter is not None:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )
            return splitter.split_documents(docs)

        split_docs = []
        for doc in docs:
            split_docs.extend(self._fallback_split(doc))
        return split_docs

    def load_and_split(self, path: Path) -> list["Document"]:
        """Legacy compatibility method. Calls load_file."""
        return self.load_file(path)

    def _fallback_split(self, doc: "Document") -> list["Document"]:
        """Simple character-based fallback splitter when LangChain splitters are absent."""
        text = doc.page_content
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end]
            meta = doc.metadata.copy()
            meta["chunk_start"] = start
            meta["chunk_end"] = min(end, len(text))
            chunks.append(Document(page_content=chunk_text, metadata=meta))
            if end >= len(text):
                break
            start += self.chunk_size - self.chunk_overlap
        return chunks

    def ingest(self, source: Any, metadata: dict[str, Any] | None = None) -> int:
        """Unified ingestion method. Detects source type and ingests into RAG memory."""
        source_str = str(source).strip()
        docs: list[Document] = []

        if source_str.startswith(("http://", "https://")):
            docs = self.load_url(source_str, metadata=metadata)
        else:
            try:
                path = Path(source)
                if path.exists():
                    docs = self.load_file(path, metadata=metadata)
                else:
                    docs = self.load_text(source_str, metadata=metadata)
            except Exception:
                docs = self.load_text(source_str, metadata=metadata)

        if not docs:
            return 0

        if self.retriever:
            self.retriever.ingest(docs)
        else:
            logger.warning("No retriever configured on DocumentIngestor. Documents split but not saved.")

        return len(docs)


class HybridRetriever:
    """Hybrid Retriever combining Dense Vector, BM25, and Cross-Encoder."""

    def __init__(self, db_dir: Path, collection_name: str = "amberclaw_docs"):
        if not _RAG_ENABLED:
            raise ImportError("LangChain or vector DB/OpenAI dependencies missing")

        self.db_dir = db_dir
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self.embeddings = OpenAIEmbeddings()

        self.vector_store = Chroma(
            collection_name=self.collection_name,
            persist_directory=str(self.db_dir),
            embedding_function=self.embeddings,
        )

        self.bm25_path = self.db_dir / "bm25_retriever.pkl"
        self.docs_path = self.db_dir / "bm25_docs.pkl"

        self.bm25_docs: list[Document] = []
        self.bm25_retriever: Any = None

        self._load_bm25_index()

    def _load_bm25_index(self) -> None:
        """Load persisted BM25 index and documents from disk."""
        if self.docs_path.exists() and self.bm25_path.exists():
            try:
                with self.docs_path.open("rb") as f:
                    self.bm25_docs = pickle.load(f)
                with self.bm25_path.open("rb") as f:
                    self.bm25_retriever = pickle.load(f)
                logger.info(
                    f"Loaded BM25 index with {len(self.bm25_docs)} "
                    "documents from disk.",
                )
            except Exception as e:
                logger.error(
                    f"Failed to load persisted BM25 index: {e}. "
                    "Reinitializing empty.",
                )
                self.bm25_docs = []
                self.bm25_retriever = None

    def ingest(self, docs: list["Document"]) -> None:
        """Add documents to the retriever."""
        if not docs:
            return

        # Add to vector store
        self.vector_store.add_documents(docs)

        # Merge with existing documents
        self.bm25_docs.extend(docs)

        # Re-initialize BM25
        self.bm25_retriever = BM25Retriever.from_documents(self.bm25_docs)
        self.bm25_retriever.k = 5

        # Persist to disk
        try:
            with self.docs_path.open("wb") as f:
                pickle.dump(self.bm25_docs, f)
            with self.bm25_path.open("wb") as f:
                pickle.dump(self.bm25_retriever, f)
            logger.info(
                f"Ingested and persisted {len(docs)} document chunks "
                f"(total: {len(self.bm25_docs)}).",
            )
        except Exception as e:
            logger.error(f"Failed to persist BM25 index to disk: {e}")

    def get_retriever(self, top_k: int = 5, filter: dict[str, Any] | None = None) -> "Any":
        """Build and return the hybrid contextual compression retriever."""
        search_kwargs = {"k": top_k * 2}
        if filter:
            search_kwargs["filter"] = filter

        if not self.bm25_retriever:
            logger.warning(
                "BM25 index not initialized. Falling back to Vector-only.",
            )
            base_retriever = self.vector_store.as_retriever(
                search_kwargs=search_kwargs,
            )
        else:
            vector_retriever = self.vector_store.as_retriever(
                search_kwargs=search_kwargs,
            )
            base_retriever = EnsembleRetriever(
                retrievers=[self.bm25_retriever, vector_retriever],
                weights=[0.3, 0.7],
            )

        try:
            model = HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-base")
            compressor = CrossEncoderReranker(model=model, top_n=top_k)
            return ContextualCompressionRetriever(
                base_compressor=compressor,
                base_retriever=base_retriever,
            )
        except Exception as e:
            logger.error(
                f"Failed to load reranker: {e}. "
                "Falling back to base retriever.",
            )
            return base_retriever
