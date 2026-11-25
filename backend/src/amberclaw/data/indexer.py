"""Data-science document indexing entry point.

The hybrid vector/keyword index is implemented in :mod:`amberclaw.rag.indexer`.
This module re-exports it for the ``amberclaw.data`` namespace.
"""

from amberclaw.rag.indexer import DocumentIndex

__all__ = ["DocumentIndex"]
