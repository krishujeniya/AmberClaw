"""Data-science knowledge base entry point.

The ingestion/indexing/context facade is implemented once in
:mod:`amberclaw.rag.knowledge_base`. This module re-exports it so data-science
agents and tools can build grounded context from the shared RAG stack.
"""

from amberclaw.rag.knowledge_base import KnowledgeBase

__all__ = ["KnowledgeBase"]
