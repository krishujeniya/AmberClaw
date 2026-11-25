"""High-level Knowledge Base facade coordinating ingestion, indexing, and context synthesis."""

from typing import Any

from loguru import logger

from amberclaw.rag.chunker import Chunk, TextChunker
from amberclaw.rag.embedder import BaseEmbedder, DeterministicHashEmbedder
from amberclaw.rag.indexer import DocumentIndex
from amberclaw.rag.retriever import DocumentRetriever, RetrievalResult


class KnowledgeBase:
    """Unified knowledge base for ingestion, semantic indexing, and grounded context generation."""

    def __init__(
        self,
        chunk_size: int = 400,
        chunk_overlap: int = 40,
        embedder: BaseEmbedder | None = None,
    ) -> None:
        self.chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.embedder = embedder or DeterministicHashEmbedder()
        self.index = DocumentIndex()
        self.retriever = DocumentRetriever(index=self.index, embedder=self.embedder)
        self._doc_ids: set[str] = set()

    @property
    def document_count(self) -> int:
        """Count of distinct ingested documents."""
        return len(self._doc_ids)

    @property
    def chunk_count(self) -> int:
        """Total count of indexed chunks."""
        return self.index.total_chunks

    def add_document(
        self,
        doc_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """Ingest, chunk, embed, and index a document."""
        meta = metadata or {}
        meta["doc_id"] = doc_id
        chunks = self.chunker.chunk_text(text, metadata=meta)

        if chunks:
            texts = [c.text for c in chunks]
            embeddings = self.embedder.embed_batch(texts)
            self.index.add_chunks(chunks, embeddings)

        self._doc_ids.add(doc_id)
        logger.info("Ingested document '{}' ({} chunks)", doc_id, len(chunks))
        return chunks

    def add_documents(
        self,
        documents: list[dict[str, Any]],
        text_field: str = "content",
        id_field: str = "id",
    ) -> int:
        """Batch ingest a collection of documents."""
        total_chunks = 0
        for doc in documents:
            doc_id = str(doc.get(id_field, f"doc-{len(self._doc_ids) + 1}"))
            text = str(doc.get(text_field, ""))
            meta = {k: v for k, v in doc.items() if k not in (text_field, id_field)}
            chunks = self.add_document(doc_id=doc_id, text=text, metadata=meta)
            total_chunks += len(chunks)
        return total_chunks

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        mode: str = "hybrid",
    ) -> list[RetrievalResult]:
        """Query knowledge base using hybrid, vector, or keyword retrieval."""
        if mode == "vector":
            return self.retriever.retrieve_vector(query_text, top_k=top_k)
        if mode == "keyword":
            return self.retriever.retrieve_keyword(query_text, top_k=top_k)
        return self.retriever.retrieve_hybrid(query_text, top_k=top_k)

    def build_context_block(
        self,
        query_text: str,
        top_k: int = 3,
        mode: str = "hybrid",
    ) -> str:
        """Generate a formatted markdown context block for LLM prompt augmentation."""
        results = self.query(query_text, top_k=top_k, mode=mode)
        if not results:
            return ""

        context_lines = ["### Grounded Knowledge Base Context:"]
        for idx, res in enumerate(results, 1):
            doc_id = res.chunk.metadata.get("doc_id", "unknown")
            context_lines.append(
                f"\n[Source {idx} - Doc: {doc_id} (Relevance: {res.score:.2f})]"
            )
            context_lines.append(res.chunk.text)

        return "\n".join(context_lines)

    def clear(self) -> None:
        """Reset the knowledge base."""
        self.index.clear()
        self._doc_ids.clear()
