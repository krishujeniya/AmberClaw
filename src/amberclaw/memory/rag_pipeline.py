# ruff: noqa: A002, ARG002, PLR0912
"""RAG Pipeline for AmberClaw.

Implements Document Ingestion (multi-format) and Hybrid Retrieval
(Vector + BM25 + Cross-Encoder Reranking).
"""

import hashlib
import json
import time
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from amberclaw.memory.sanitizer import MemorySanitizer

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
    logger.debug(
        f"RAG dependencies missing. Install with `pip install amberclaw[docs,vectordb]`. {e}"
    )
    _RAG_ENABLED = False
    DirectoryLoader = None  # type: ignore
    UnstructuredFileLoader = None  # type: ignore
    RecursiveCharacterTextSplitter = None  # type: ignore

    class Document:  # type: ignore
        """Fallback Document stub class when LangChain is not installed."""

        def __init__(self, page_content: str, metadata: dict[str, Any] | None = None):
            self.page_content = page_content
            self.metadata = metadata or {}

    class FallbackRetriever:  # type: ignore
        def __init__(
            self, docs: list[Any], search_kwargs: dict[str, Any] | None = None
        ) -> None:
            self.docs = docs
            self.search_kwargs = search_kwargs or {}

        def invoke(self, query: str) -> list[Any]:
            k = self.search_kwargs.get("k", 5)
            filtered = self.docs
            f = self.search_kwargs.get("filter")
            if isinstance(f, dict):
                org = f.get("org_id")
                if org:
                    filtered = [
                        d
                        for d in filtered
                        if getattr(d, "metadata", {}).get("org_id") == org
                    ]
            return filtered[:k]

        def get_relevant_documents(self, query: str) -> list[Any]:
            return self.invoke(query)

    class FallbackVectorStore:  # type: ignore
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.docs: list[Any] = []

        def add_documents(self, docs: list[Any]) -> None:
            self.docs.extend(docs)

        def as_retriever(
            self, search_kwargs: dict[str, Any] | None = None
        ) -> FallbackRetriever:
            return FallbackRetriever(self.docs, search_kwargs)

        def delete(
            self,
            ids: list[str] | None = None,
            where: dict[str, Any] | None = None,
        ) -> None:
            if ids:
                self.docs = [
                    d
                    for d in self.docs
                    if getattr(d, "metadata", {}).get("doc_id") not in ids
                ]
            if where and "org_id" in where:
                self.docs = [
                    d
                    for d in self.docs
                    if getattr(d, "metadata", {}).get("org_id") != where["org_id"]
                ]

    class FallbackBM25:  # type: ignore
        def __init__(self, docs: list[Any] | None = None) -> None:
            self.docs = list(docs or [])
            self.k = 5

        @classmethod
        def from_documents(cls, docs: list[Any]) -> "FallbackBM25":
            return cls(docs)

        def add_documents(self, docs: list[Any]) -> None:
            self.docs.extend(docs)

        def invoke(self, query: str) -> list[Any]:
            return self.docs[: self.k]

        def get_relevant_documents(self, query: str) -> list[Any]:
            return self.docs[: self.k]

    class FallbackOpenAIEmbeddings:  # type: ignore
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

    Chroma = FallbackVectorStore  # type: ignore
    OpenAIEmbeddings = FallbackOpenAIEmbeddings  # type: ignore
    BM25Retriever = FallbackBM25  # type: ignore
    EnsembleRetriever = None  # type: ignore
    ContextualCompressionRetriever = None  # type: ignore
    CrossEncoderReranker = None  # type: ignore
    HuggingFaceCrossEncoder = None  # type: ignore


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
                self.retriever = HybridRetriever(
                    db_dir, collection_name=self.collection
                )
            except Exception as e:
                logger.warning(
                    f"Could not initialize HybridRetriever for ingestion: {e}"
                )

    def load_text(
        self, text: str, source: str = "message", metadata: dict[str, Any] | None = None
    ) -> list["Document"]:
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

    def load_url(
        self, url: str, metadata: dict[str, Any] | None = None
    ) -> list["Document"]:
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

    def _load_single_file(
        self, path: Path, metadata: dict[str, Any] | None = None
    ) -> list["Document"]:
        """Loads a single file using Unstructured, falling back to a plain UTF-8 text reader."""
        if UnstructuredFileLoader is not None:
            try:
                file_loader = UnstructuredFileLoader(str(path))
                return file_loader.load()
            except Exception as e:
                logger.debug(
                    f"Unstructured loader failed: {e}. Falling back to plain text reader."
                )
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            meta = {"source": str(path)}
            if metadata:
                meta.update(metadata)
            return [Document(page_content=content, metadata=meta)]
        except Exception as ex:
            logger.error(f"Failed to read file {path} as text: {ex}")
            raise ValueError(f"Failed to read file {path}: {ex}") from ex

    def _load_directory(
        self, path: Path, metadata: dict[str, Any] | None = None
    ) -> list["Document"]:
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

    def load_file(
        self, path: Path, metadata: dict[str, Any] | None = None
    ) -> list["Document"]:
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

    def ingest(
        self,
        source: Any,
        metadata: dict[str, Any] | None = None,
        org_id: str | None = None,
    ) -> int:
        """Unified ingestion method. Detects source type and ingests into RAG memory."""
        source_str = str(source).strip()
        docs: list[Document] = []

        eff_meta = dict(metadata) if metadata else {}
        if org_id and "org_id" not in eff_meta:
            eff_meta["org_id"] = org_id

        if source_str.startswith(("http://", "https://")):
            docs = self.load_url(source_str, metadata=eff_meta)
        else:
            try:
                path = Path(source)
                if path.exists():
                    docs = self.load_file(path, metadata=eff_meta)
                else:
                    docs = self.load_text(source_str, metadata=eff_meta)
            except Exception:
                docs = self.load_text(source_str, metadata=eff_meta)

        if not docs:
            return 0

        if self.retriever:
            self.retriever.ingest(docs, org_id=org_id)
        else:
            logger.warning(
                "No retriever configured on DocumentIngestor. Documents split but not saved."
            )

        return len(docs)


class HybridRetriever:
    """Hybrid Retriever combining Dense Vector, BM25, and Cross-Encoder."""

    def __init__(
        self,
        db_dir: Path,
        collection_name: str = "amberclaw_docs",
        embedding_version: str = "v1",
    ):
        if not _RAG_ENABLED:
            logger.debug(
                "Optional RAG dependencies missing; initializing HybridRetriever with fallback storage."
            )

        self.db_dir = db_dir
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self.embedding_version = embedding_version
        self.embeddings = OpenAIEmbeddings()

        self.vector_store = Chroma(
            collection_name=self.collection_name,
            persist_directory=str(self.db_dir),
            embedding_function=self.embeddings,
        )

        self.bm25_path = self.db_dir / "bm25_retriever.json"
        self.docs_path = self.db_dir / "bm25_docs.json"

        self.bm25_docs: list[Document] = []
        self._doc_hashes: set[str] = set()
        self.bm25_retriever: Any = None
        self.last_query_metrics: dict[str, float] = {}

        self._load_bm25_index()

    @staticmethod
    def _compute_doc_hash(doc: "Document") -> str:
        """Compute deterministic hash for document deduplication."""
        content = (
            f"{doc.page_content}:{sorted(doc.metadata.items()) if doc.metadata else ''}"
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _load_bm25_index(self) -> None:
        """Load persisted BM25 index and documents from disk via JSON."""
        # Support legacy .json or current json path
        legacy_pkl = self.db_dir / "bm25_docs.pkl"
        if not self.docs_path.exists() and legacy_pkl.exists():
            logger.warning(
                "Unsafe pickle BM25 index detected on disk; skipping pickle load for security."
            )

        if self.bm25_path.exists():
            try:
                bm25_meta = json.loads(self.bm25_path.read_text(encoding="utf-8"))
                self.embedding_version = bm25_meta.get(
                    "embedding_version", self.embedding_version
                )
            except Exception as e:
                logger.debug(f"Failed to read embedding version from BM25 index: {e}")

        if self.docs_path.exists():
            try:
                data = json.loads(self.docs_path.read_text(encoding="utf-8"))
                loaded_docs = []
                for item in data:
                    page_content = item.get("page_content", "")
                    metadata = item.get("metadata", {})
                    # Reconstruct Document object
                    doc = Document(page_content=page_content, metadata=metadata)
                    loaded_docs.append(doc)
                    self._doc_hashes.add(self._compute_doc_hash(doc))
                self.bm25_docs = loaded_docs
                if self.bm25_docs:
                    self.bm25_retriever = BM25Retriever.from_documents(self.bm25_docs)
                    self.bm25_retriever.k = 5
                logger.info(
                    f"Loaded BM25 index with {len(self.bm25_docs)} "
                    "documents from JSON disk persistence.",
                )
            except Exception as e:
                logger.error(
                    f"Failed to load persisted BM25 index from JSON: {e}. Reinitializing empty.",
                )
                self.bm25_docs = []
                self._doc_hashes.clear()
                self.bm25_retriever = None

    def _persist_index(self, new_chunks_indexed: int = 0) -> None:
        """Persist BM25 document inventory and metadata to disk."""
        try:
            serialized_docs = [
                {"page_content": d.page_content, "metadata": d.metadata}
                for d in self.bm25_docs
            ]
            content = json.dumps(serialized_docs, ensure_ascii=False, indent=2)
            self.docs_path.write_text(content, encoding="utf-8")
            self.bm25_path.write_text(
                json.dumps(
                    {
                        "status": "ready",
                        "doc_count": len(self.bm25_docs),
                        "new_chunks_indexed": new_chunks_indexed,
                        "embedding_version": self.embedding_version,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"Failed to persist BM25 index to disk: {e}")

    def ingest(self, docs: list["Document"], org_id: str | None = None) -> int:
        """Incrementally add documents to the retriever, skipping duplicates.

        Applies input sanitization against prompt injection, records document
        versioning/provenance, and enforces deduplication.
        """
        if not docs:
            return 0

        # Sanitize and augment provenance metadata
        for d in docs:
            cleaned, detected = MemorySanitizer.sanitize_text(d.page_content)
            d.page_content = cleaned
            if detected:
                d.metadata["poisoning_detected"] = True
                logger.warning(
                    "Sanitized potential prompt injection/poisoning in ingested document chunk."
                )

            if org_id and not d.metadata.get("org_id"):
                d.metadata["org_id"] = org_id

            if "version" not in d.metadata:
                d.metadata["version"] = 1

            if "created_at" not in d.metadata:
                d.metadata["created_at"] = datetime.now(UTC).isoformat()

            if "doc_id" not in d.metadata:
                d.metadata["doc_id"] = self._compute_doc_hash(d)[:16]

        # Filter duplicates via hash index
        new_docs: list[Document] = []
        for d in docs:
            h = self._compute_doc_hash(d)
            if h not in self._doc_hashes:
                self._doc_hashes.add(h)
                new_docs.append(d)

        if not new_docs:
            logger.debug(
                "All documents already indexed in BM25; skipping duplicate ingestion."
            )
            return 0

        # Add to vector store
        self.vector_store.add_documents(new_docs)

        # Merge with existing documents
        self.bm25_docs.extend(new_docs)

        # Incremental retriever update or rebuild if required
        if self.bm25_retriever is not None and hasattr(
            self.bm25_retriever, "add_documents"
        ):
            try:
                self.bm25_retriever.add_documents(new_docs)
            except Exception:
                self.bm25_retriever = BM25Retriever.from_documents(self.bm25_docs)
        else:
            self.bm25_retriever = BM25Retriever.from_documents(self.bm25_docs)

        self.bm25_retriever.k = 5

        # Persist to disk as JSON
        self._persist_index(new_chunks_indexed=len(new_docs))
        logger.info(
            f"Incrementally ingested {len(new_docs)} document chunks "
            f"(total: {len(self.bm25_docs)}).",
        )
        return len(new_docs)

    def _delete_matching(self, predicate: Any) -> int:
        """Helper to remove matching documents across BM25 and vector store."""
        to_delete = [d for d in self.bm25_docs if predicate(d)]
        if not to_delete:
            return 0

        deleted_ids: list[str] = []
        for d in to_delete:
            h = self._compute_doc_hash(d)
            self._doc_hashes.discard(h)
            doc_id = d.metadata.get("doc_id")
            if doc_id:
                deleted_ids.append(str(doc_id))

        self.bm25_docs = [d for d in self.bm25_docs if not predicate(d)]

        # Rebuild BM25 retriever
        if self.bm25_docs:
            self.bm25_retriever = BM25Retriever.from_documents(self.bm25_docs)
            self.bm25_retriever.k = 5
        else:
            self.bm25_retriever = None

        # Propagate deletion to vector store if supported
        if hasattr(self.vector_store, "delete"):
            try:
                if deleted_ids:
                    self.vector_store.delete(ids=deleted_ids)
            except Exception as e:
                logger.debug(f"Vector store delete not supported or failed: {e}")

        # Update disk persistence
        self._persist_index()
        return len(to_delete)

    def delete_document(self, doc_id: str, org_id: str | None = None) -> int:
        """Delete document chunk by doc_id (and optional tenant scope)."""

        def pred(d: Document) -> bool:
            match_id = (
                str(d.metadata.get("doc_id", "")) == str(doc_id)
                or str(d.metadata.get("id", "")) == str(doc_id)
                or self._compute_doc_hash(d) == str(doc_id)
            )
            if not match_id:
                return False
            return not (org_id and d.metadata.get("org_id") != org_id)

        return self._delete_matching(pred)

    def delete_by_source(self, source_uri: str, org_id: str | None = None) -> int:
        """Delete all document chunks from a specific source URI."""

        def pred(d: Document) -> bool:
            match_src = (
                str(d.metadata.get("source", "")) == str(source_uri)
                or str(d.metadata.get("source_uri", "")) == str(source_uri)
                or str(d.metadata.get("url", "")) == str(source_uri)
            )
            if not match_src:
                return False
            return not (org_id and d.metadata.get("org_id") != org_id)

        return self._delete_matching(pred)

    def delete_by_session(self, session_id: str, org_id: str | None = None) -> int:
        """Delete all document chunks associated with a session ID."""

        def pred(d: Document) -> bool:
            if str(d.metadata.get("session_id", "")) != str(session_id):
                return False
            return not (org_id and d.metadata.get("org_id") != org_id)

        return self._delete_matching(pred)

    def migrate_embeddings(
        self,
        new_embeddings: Any,
        new_version: str,
        new_collection_name: str | None = None,
    ) -> int:
        """Migrate vector store to new embedding model or version, reindexing all docs."""
        self.embeddings = new_embeddings
        self.embedding_version = new_version
        if new_collection_name:
            self.collection_name = new_collection_name

        try:
            self.vector_store = Chroma(
                collection_name=self.collection_name,
                persist_directory=str(self.db_dir),
                embedding_function=self.embeddings,
            )
            if self.bm25_docs:
                self.vector_store.add_documents(self.bm25_docs)
        except Exception as e:
            logger.error(f"Failed to re-initialize vector store during migration: {e}")
            raise

        self._persist_index()
        logger.info(
            f"Successfully migrated {len(self.bm25_docs)} documents to embedding version {new_version}."
        )
        return len(self.bm25_docs)

    def get_retriever(
        self,
        top_k: int = 5,
        filter: dict[str, Any] | None = None,
        org_id: str | None = None,
    ) -> "Any":
        """Build and return the hybrid contextual compression retriever with tenant pre-filtering."""
        search_kwargs: dict[str, Any] = {"k": top_k * 2}

        # Resolve target tenant
        target_org = org_id
        if not target_org and isinstance(filter, dict):
            target_org = filter.get("org_id")

        # Chroma filter: ensure org_id is present
        effective_filter = filter
        if target_org:
            if effective_filter:
                if (
                    isinstance(effective_filter, dict)
                    and "org_id" not in effective_filter
                ):
                    effective_filter = {
                        "$and": [{"org_id": target_org}, effective_filter]
                    }
            else:
                effective_filter = {"org_id": target_org}

        if effective_filter:
            search_kwargs["filter"] = effective_filter

        # Tenant pre-filtering for BM25
        active_bm25 = self.bm25_retriever
        if target_org:
            org_docs = [
                d for d in self.bm25_docs if d.metadata.get("org_id") == target_org
            ]
            if org_docs:
                active_bm25 = BM25Retriever.from_documents(org_docs)
                active_bm25.k = top_k
            else:
                active_bm25 = None

        if not active_bm25:
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
            if EnsembleRetriever is not None:
                base_retriever = EnsembleRetriever(
                    retrievers=[active_bm25, vector_retriever],
                    weights=[0.3, 0.7],
                )
            else:
                base_retriever = active_bm25

        if CrossEncoderReranker is not None and HuggingFaceCrossEncoder is not None:
            try:
                model = HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-base")
                compressor = CrossEncoderReranker(model=model, top_n=top_k)
                if ContextualCompressionRetriever is not None:
                    return ContextualCompressionRetriever(
                        base_compressor=compressor,
                        base_retriever=base_retriever,
                    )
            except Exception as e:
                logger.debug(
                    f"Failed to load reranker: {e}. Falling back to base retriever."
                )
        return base_retriever

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        org_id: str | None = None,
        filter: dict[str, Any] | None = None,
    ) -> list["Document"]:
        """Retrieve documents using the hybrid ensemble with strict tenant-scoping."""
        start_t = time.perf_counter()
        retriever = self.get_retriever(top_k=top_k, filter=filter, org_id=org_id)
        if retriever is None:
            self.last_query_metrics = {"total_ms": 0.0}
            return []

        raw_docs: list[Document] = []
        try:
            if hasattr(retriever, "invoke"):
                raw_docs = retriever.invoke(query)
            elif hasattr(retriever, "get_relevant_documents"):
                raw_docs = retriever.get_relevant_documents(query)
        except Exception as e:
            logger.warning(f"Retriever query failed: {e}")
            self.last_query_metrics = {
                "total_ms": round((time.perf_counter() - start_t) * 1000.0, 3)
            }
            return []

        # Strict post-retrieval verification to prevent cross-tenant leakage and deduplicate
        unique_docs: list[Document] = []
        seen_hashes: set[str] = set()
        for d in raw_docs:
            if org_id and getattr(d, "metadata", {}).get("org_id") != org_id:
                continue
            h = self._compute_doc_hash(d)
            if h not in seen_hashes:
                seen_hashes.add(h)
                unique_docs.append(d)

        total_ms = (time.perf_counter() - start_t) * 1000.0
        self.last_query_metrics = {"total_ms": round(total_ms, 3)}
        return unique_docs[:top_k]
