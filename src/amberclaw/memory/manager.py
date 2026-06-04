# ruff: noqa: PLR0912, PLR0913, PLR0915
"""Orchestrator for the AmberClaw Memory System."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from loguru import logger

# Import sub-modules
from amberclaw.memory.base import ScopeContext
from amberclaw.memory.frozen_memory import FrozenSnapshotMemory
from amberclaw.memory.rag_pipeline import HybridRetriever
from amberclaw.memory.session_db import SessionDB

try:
    from langchain_core.documents import Document
except ImportError:
    class Document:  # type: ignore
        """Fallback Document stub class when LangChain is not installed."""

        def __init__(self, page_content: str, metadata: dict[str, Any] | None = None):
            self.page_content = page_content
            self.metadata = metadata or {}


class MemoryManager:
    """Orchestrates the 3-layer memory system (Hybrid, Context, and Tools recall modes).

    Supports write frequencies: turn, async, session, or N turns.
    """

    def __init__(
        self,
        workspace: Path | None = None,
        recall_mode: str = "hybrid",
        write_frequency: str | int = "turn",
    ):
        self.workspace = workspace or Path("~/.amberclaw/workspace").expanduser()
        self.recall_mode = recall_mode.lower()
        self.write_frequency = write_frequency

        # Initialize sub-components
        self.session_db = SessionDB(self.workspace / "memory" / "sessions.db")
        try:
            self.hybrid_retriever = HybridRetriever(
                db_dir=self.workspace / "memory" / "chroma",
            )
        except ImportError:
            logger.warning("HybridRetriever disabled (LangChain/Chroma dependencies not installed)")
            self.hybrid_retriever = None
        self.frozen_memory = FrozenSnapshotMemory(workspace=self.workspace)

        # Buffering for RAG vector ingestion
        self.turn_buffers: dict[str, list[Document]] = {}
        self.background_tasks: set[asyncio.Task] = set()

    async def add_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        scope_context: ScopeContext | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        org_id: str | None = None,
    ) -> None:
        """Add a turn to the session database and trigger RAG indexing based on frequency."""
        if scope_context:
            user_id = user_id or scope_context.user_id
            agent_id = agent_id or scope_context.agent_id
            session_id = session_id or scope_context.session_id or ""
            org_id = org_id or scope_context.org_id

        # 1. Immediate write to SQLite transaction database to ensure persistence
        turn_id = self.session_db.add_turn(
            session_id=session_id,
            role=role,
            content=content,
            metadata=metadata,
            user_id=user_id,
            agent_id=agent_id,
            org_id=org_id,
        )

        # Create virtual Document stub for ingestion
        doc = Document(
            page_content=content,
            metadata={
                "session_id": session_id,
                "role": role,
                "turn_id": turn_id,
                "user_id": user_id or "",
                "agent_id": agent_id or "",
                "org_id": org_id or "",
                **(metadata or {}),
            },
        )

        # 2. Handle RAG indexing based on frequency configuration
        if self.hybrid_retriever:
            if self.write_frequency == "turn":
                self.hybrid_retriever.ingest([doc])

            elif self.write_frequency == "async":
                task = asyncio.create_task(
                    asyncio.to_thread(self.hybrid_retriever.ingest, [doc]),
                )
                self.background_tasks.add(task)
                task.add_done_callback(self.background_tasks.discard)

            elif self.write_frequency == "session":
                if session_id not in self.turn_buffers:
                    self.turn_buffers[session_id] = []
                self.turn_buffers[session_id].append(doc)

            elif isinstance(self.write_frequency, int):
                if session_id not in self.turn_buffers:
                    self.turn_buffers[session_id] = []
                self.turn_buffers[session_id].append(doc)

                if len(self.turn_buffers[session_id]) >= self.write_frequency:
                    await self.flush(session_id)
        # If hybrid retriever is disabled, still buffer turns for compatibility
        elif self.write_frequency == "session":
            if session_id not in self.turn_buffers:
                self.turn_buffers[session_id] = []
            self.turn_buffers[session_id].append(doc)
        elif isinstance(self.write_frequency, int):
            if session_id not in self.turn_buffers:
                self.turn_buffers[session_id] = []
            self.turn_buffers[session_id].append(doc)
            if len(self.turn_buffers[session_id]) >= self.write_frequency:
                self.turn_buffers.pop(session_id, None)

    async def recall(
        self,
        query: str,
        session_id: str | None = None,
        limit: int = 5,
        scope_context: ScopeContext | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        org_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant context based on recall mode and scope boundaries."""
        if scope_context:
            user_id = user_id or scope_context.user_id
            agent_id = agent_id or scope_context.agent_id
            session_id = session_id or scope_context.session_id
            org_id = org_id or scope_context.org_id

        if self.recall_mode == "hybrid":
            # Semantic RAG search (Vector + BM25)
            rag_docs = []
            if self.hybrid_retriever:
                # Build metadata filter for vector store
                or_clauses = []
                if session_id:
                    or_clauses.append({"session_id": session_id})
                if user_id:
                    or_clauses.append({"user_id": user_id})
                if agent_id:
                    or_clauses.append({"agent_id": agent_id})
                if org_id:
                    or_clauses.append({"org_id": org_id})

                filter_dict = None
                if or_clauses:
                    filter_dict = {"$or": or_clauses} if len(or_clauses) > 1 else or_clauses[0]

                retriever = self.hybrid_retriever.get_retriever(top_k=limit, filter=filter_dict)
                if retriever:
                    try:
                        raw_rag_docs = retriever.invoke(query)
                        # Secure post-filtering to prevent cross-tenant/cross-scope leakage
                        for doc in raw_rag_docs:
                            doc_sess = doc.metadata.get("session_id")
                            doc_user = doc.metadata.get("user_id")
                            doc_ag = doc.metadata.get("agent_id")
                            doc_org = doc.metadata.get("org_id")

                            match = False
                            if session_id and doc_sess == session_id:
                                match = True
                            if user_id and doc_user == user_id:
                                match = True
                            if agent_id and doc_ag == agent_id:
                                match = True
                            if org_id and doc_org == org_id:
                                match = True

                            # If no filters set, allow everything
                            if not (session_id or user_id or agent_id or org_id):
                                match = True

                            if match:
                                rag_docs.append(doc)
                    except Exception as e:
                        logger.warning(f"RAG retriever invoke failed: {e}")

            # Full-text search (FTS5 matched turns, hierarchical/OR-ed)
            fts_turns = self.session_db.search_turns(
                query=query,
                session_id=session_id,
                user_id=user_id,
                agent_id=agent_id,
                org_id=org_id,
                hierarchical=True,
            )

            results = []
            seen_ids = set()

            # Add RAG documents
            for doc in rag_docs:
                doc_id = doc.metadata.get("turn_id")
                if doc_id:
                    seen_ids.add(doc_id)
                results.append(
                    {
                        "source": "rag",
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                    },
                )

            # Add FTS turns
            for turn in fts_turns[:limit]:
                if turn["id"] not in seen_ids:
                    results.append(
                        {
                            "source": "fts",
                            "content": turn["content"],
                            "metadata": {
                                "role": turn["role"],
                                "turn_index": turn["turn_index"],
                                "timestamp": turn["timestamp"],
                                "user_id": turn["user_id"],
                                "agent_id": turn["agent_id"],
                                "org_id": turn["org_id"],
                                **turn["metadata"],
                            },
                        },
                    )

            return results

        if self.recall_mode == "context":
            # Retrieve last turns directly matching hierarchy
            turns = self.session_db.get_turns(
                session_id=session_id,
                user_id=user_id,
                agent_id=agent_id,
                org_id=org_id,
                hierarchical=True,
            )
            recent_turns = turns[-limit:] if len(turns) >= limit else turns
            return [
                {
                    "source": "context",
                    "content": t["content"],
                    "metadata": {
                        "role": t["role"],
                        "turn_index": t["turn_index"],
                        "timestamp": t["timestamp"],
                        "user_id": t["user_id"],
                        "agent_id": t["agent_id"],
                        "org_id": t["org_id"],
                        **t["metadata"],
                    },
                }
                for t in recent_turns
            ]

        if self.recall_mode == "tools":
            # Empty list; retrieval is delegated to agent invoking tools explicitly
            return []

        return []

    async def flush(self, session_id: str) -> None:
        """Flush buffered turns into the vector store."""
        docs = self.turn_buffers.pop(session_id, [])
        if docs and self.hybrid_retriever:
            logger.info(f"Flushing {len(docs)} buffered turns to vector store.")
            self.hybrid_retriever.ingest(docs)

    def close(self) -> None:
        """Close connections."""
        self.session_db.close()


memory = MemoryManager()
