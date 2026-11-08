# ruff: noqa: PLC0415, PLR0913
"""AmberClaw Memory Manager.

Abstracts Mem0 v1.0+ and provides persistent Vector DB backends,
multi-scope memory tracking, and basic fact extraction.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import gettempdir
from typing import Any

from loguru import logger

from amberclaw.memory.base import ScopeContext

try:
    from mem0 import Memory
except ImportError:
    Memory = None


class MemoryManager:
    """Manages long-term conversational memory and facts using Mem0."""

    def __init__(self, workspace: Path, provider: str = "chroma") -> None:
        self.workspace = workspace
        self.provider = provider
        # Guard against mock objects or invalid filesystem paths
        is_mock = type(workspace).__name__ in ("Mock", "MagicMock") or str(
            workspace
        ).startswith("<")
        if not isinstance(workspace, Path) or is_mock:
            self.db_path = Path(gettempdir()) / "amberclaw-disabled-memory"
            self._memory = None
            self._graph = None
            return

        self.db_path = workspace / "mem0_db"
        self.db_path.mkdir(parents=True, exist_ok=True)
        self._memory = self._init_mem0()

        from amberclaw.memory.graph_memory import TemporalGraphMemory

        self._graph = TemporalGraphMemory(self.db_path / "graph_memory.json")

    def _init_mem0(self) -> Any:
        if Memory is None:
            logger.warning("mem0ai package not installed. Memory features disabled.")
            return None

        try:
            config = {
                "vector_store": {
                    "provider": self.provider,
                    "config": {
                        "path": str(self.db_path),
                    },
                },
                "version": "v1.1",  # Using v1+ features
            }
            logger.info("Initializing Mem0 with {} at {}", self.provider, self.db_path)
            return Memory.from_config(config)
        except Exception as e:
            logger.error("Failed to initialize Mem0: {}", e)
            return None

    def search(
        self,
        query: str,
        user_id: str | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
        org_id: str | None = None,
        scope_context: ScopeContext | None = None,
    ) -> list[str]:
        """Search memory with multi-scope support."""
        if scope_context:
            user_id = user_id or scope_context.user_id
            agent_id = agent_id or scope_context.agent_id
            session_id = session_id or scope_context.session_id
            org_id = org_id or scope_context.org_id

        if not self._memory:
            return []

        try:
            # Mem0 v1.0+ supports user_id, agent_id, session_id natively
            # We pass org_id in metadata/filters if supported, or via standard custom metadata
            metadata = {"org_id": org_id} if org_id else None
            results = self._memory.search(
                query,
                user_id=user_id,
                agent_id=agent_id,
                run_id=session_id,
                metadata=metadata,
            )

            facts = []
            for m in results:
                val = None
                if isinstance(m, dict):
                    val = m.get("memory")
                elif hasattr(m, "memory"):
                    val = m.memory
                if val:
                    facts.append(str(val))
            return facts
        except Exception as e:
            logger.error("Memory search failed: {}", e)
            return []

    def add(
        self,
        text: str,
        user_id: str | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
        org_id: str | None = None,
        scope_context: ScopeContext | None = None,
    ) -> None:
        """Add to memory with multi-scope support."""
        if scope_context:
            user_id = user_id or scope_context.user_id
            agent_id = agent_id or scope_context.agent_id
            session_id = session_id or scope_context.session_id
            org_id = org_id or scope_context.org_id

        if not self._memory:
            return

        try:
            metadata = {"org_id": org_id} if org_id else None
            self._memory.add(
                text,
                user_id=user_id,
                agent_id=agent_id,
                run_id=session_id,
                metadata=metadata,
            )

        except Exception as e:
            logger.error("Memory add failed: {}", e)
