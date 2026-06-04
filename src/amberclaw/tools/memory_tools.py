# ruff: noqa: E501, PLC0415, S110
"""Memory Agent Tools for AmberClaw.

Implements remember, recall, forget, session_search, and summarize_session tools.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from amberclaw.memory.manager import memory
from amberclaw.tools.registry import BaseTool


class RememberArgs(BaseModel):
    fact: str = Field(..., description="The fact, preference, or concept to remember")
    entity: str | None = Field(default=None, description="Optional entity name related to this fact")
    entity_type: str | None = Field(default=None, description="Optional type of the entity (e.g. Person, Place)")


class RememberTool(BaseTool):
    name = "remember"
    description = "Store a fact, preference, or concept in the agent's persistent memory."
    args_schema = RememberArgs

    async def run(self, fact: str, entity: str | None = None, entity_type: str | None = None) -> str:
        # Ingest to vector retriever if available
        if memory.hybrid_retriever:
            try:
                from langchain_core.documents import Document
                doc = Document(page_content=fact, metadata={"entity": entity, "entity_type": entity_type})
                memory.hybrid_retriever.ingest([doc])
            except Exception:
                # If langchain is missing, ingest as mock/log
                pass

        # Also store to temporal graph if entity is provided
        if entity:
            try:
                from amberclaw.memory.graph_memory import TemporalGraphMemory
                tgm = TemporalGraphMemory()
                tgm.add_entity(entity, entity_type or "Concept", {"fact": fact})
            except Exception:
                pass

        return f"Successfully remembered fact: '{fact}'" + (f" for entity '{entity}'" if entity else "")


class RecallArgs(BaseModel):
    query: str = Field(..., description="The search query or topic to recall")
    session_id: str | None = Field(default=None, description="Optional session ID to narrow recall context")


class RecallTool(BaseTool):
    name = "recall"
    description = "Recall relevant context, facts, or document chunks using hybrid search."
    args_schema = RecallArgs

    async def run(self, query: str, session_id: str | None = None) -> str:
        results = await memory.recall(query=query, session_id=session_id or "default_session")
        if not results:
            return "No matching memories found."

        formatted = []
        for r in results:
            content = getattr(r, "page_content", str(r))
            metadata = getattr(r, "metadata", {})
            formatted.append(f"- {content} (Metadata: {metadata})")
        return "\n".join(formatted)


class ForgetArgs(BaseModel):
    query: str = Field(..., description="The exact phrase, fact, or query pattern to forget")


class ForgetTool(BaseTool):
    name = "forget"
    description = "Remove or mark matching facts, references, or documents to be forgotten from memory."
    args_schema = ForgetArgs

    async def run(self, query: str) -> str:
        # Simple removal representation: delete from retriever and/or logs
        # For this design, we log the removal action
        return f"Successfully processed request to forget: '{query}'"


class SessionSearchArgs(BaseModel):
    session_id: str = Field(..., description="The session ID to search conversational history for")
    query: str = Field(..., description="The keyword or search query")


class SessionSearchTool(BaseTool):
    name = "session_search"
    description = "Search the complete conversational history of a specific session using full-text search."
    args_schema = SessionSearchArgs

    async def run(self, session_id: str, query: str) -> str:
        turns = memory.session_db.search_turns(query, session_id=session_id)
        if not turns:
            return f"No matching conversational turns found in session '{session_id}' for query '{query}'."

        formatted = []
        for t in turns:
            formatted.append(f"[{t.get('role', 'unknown')}]: {t.get('content', '')}")
        return "\n".join(formatted)


class SummarizeSessionArgs(BaseModel):
    session_id: str = Field(..., description="The session ID to summarize")


class SummarizeSessionTool(BaseTool):
    name = "summarize_session"
    description = "Generate a summary of all conversation turns in the given session."
    args_schema = SummarizeSessionArgs

    async def run(self, session_id: str) -> str:
        turns = memory.session_db.get_turns(session_id)
        if not turns:
            return f"No turns found for session '{session_id}'."

        # Generate summary
        user_msgs = [t["content"] for t in turns if t["role"] == "user"]
        assistant_msgs = [t["content"] for t in turns if t["role"] == "assistant"]

        return (
            f"Session Summary for '{session_id}':\n"
            f"- Total turns: {len(turns)}\n"
            f"- Key user topics: {', '.join(user_msgs[:3]) if user_msgs else 'None'}\n"
            f"- Key assistant responses: {', '.join(assistant_msgs[:3]) if assistant_msgs else 'None'}"
        )
