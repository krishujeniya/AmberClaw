"""Data-science text chunking entry point.

Chunking primitives live once in :mod:`amberclaw.rag.chunker`. This module
re-exports them so data-science pipelines can use the ``amberclaw.data``
namespace without a second, divergent implementation.
"""

from amberclaw.rag.chunker import Chunk, TextChunker

__all__ = ["Chunk", "TextChunker"]
