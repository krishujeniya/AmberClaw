"""Data-science document retrieval entry point.

Retrieval strategies live once in :mod:`amberclaw.rag.retriever`. This module
re-exports them for the ``amberclaw.data`` namespace.
"""

from amberclaw.rag.retriever import DocumentRetriever, RetrievalResult

__all__ = ["DocumentRetriever", "RetrievalResult"]
