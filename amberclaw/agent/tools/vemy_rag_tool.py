"""Vemy RAG Search tool — vector similarity search on knowledge base."""

from typing import Any

from loguru import logger

from amberclaw.agent.tools.base import Tool


class VemyRAGSearchTool(Tool):
    """Search the Vemy knowledge base for relevant documents."""

    name = "vemy_knowledge_search"
    description = (
        "Search Vemy's RAG knowledge base built from Google Drive documents. "
        "Returns relevant document chunks using vector similarity search. "
        "Use this when you need factual information from the user's knowledge base."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to find relevant knowledge.",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of results to return (1-10). Default: 3.",
                "minimum": 1,
                "maximum": 10,
            },
        },
        "required": ["query"],
    }

    def __init__(self, mongodb_uri: str | None = None):
        self._mongodb_uri = mongodb_uri
        self._mongo = None

    def _get_manager(self):
        """Lazy-initialize MongoDB connection."""
        if self._mongo is not None:
            return self._mongo

        from amberclaw.vemy.Tools.MongoDB import MongoDBManager
        from amberclaw.vemy.Credentials import Settings

        if self._mongodb_uri:
            Settings.Config.MONGODB_URI = self._mongodb_uri

        self._mongo = MongoDBManager()
        self._mongo.connect()
        logger.info("Vemy RAG Search: MongoDB connected")
        return self._mongo

    async def execute(self, query: str, top_k: int = 3, **kwargs: Any) -> str:
        try:
            mongo = self._get_manager()

            if not mongo.connected or not mongo.knowledge_base:
                return "Error: Knowledge base unavailable — MongoDB not connected or no knowledge base configured."

            results = mongo.knowledge_base.search_similar(query, include_metadata=True)

            if not results:
                return f"No relevant knowledge found for: '{query}'"

            output_parts = [f"Found {min(len(results), top_k)} relevant document(s):\n"]
            for i, doc in enumerate(results[:top_k], 1):
                text = doc.get("text", "")
                metadata = doc.get("metadata", {})
                source = metadata.get("source", "unknown")
                output_parts.append(f"--- Result {i} (source: {source}) ---")
                output_parts.append(text[:1000])
                output_parts.append("")

            return "\n".join(output_parts)

        except Exception as e:
            logger.error("VemyRAGSearchTool error: {}", e)
            return f"Error: Knowledge search failed — {e}"
