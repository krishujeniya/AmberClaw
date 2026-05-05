"""AmberClaw Memory Manager.

Abstracts Mem0 v1.0+ and provides persistent Vector DB backends,
multi-scope memory tracking, and basic fact extraction.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional
from loguru import logger

try:
    from mem0 import Memory
except ImportError:
    Memory = None

class MemoryManager:
    """Manages long-term conversational memory and facts using Mem0."""

    def __init__(self, workspace: Path, provider: str = "chroma"):
        self.workspace = workspace
        self.provider = provider
        self.db_path = workspace / "mem0_db"
        self.db_path.mkdir(parents=True, exist_ok=True)
        self._memory = self._init_mem0()

        from amberclaw.memory.graph_memory import TemporalKnowledgeGraph
        self._graph = TemporalKnowledgeGraph(self.db_path)

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
                "version": "v1.1" # Using v1+ features
            }
            logger.info(f"Initializing Mem0 with {self.provider} at {self.db_path}")
            return Memory.from_config(config)
        except Exception as e:
            logger.error(f"Failed to initialize Mem0: {e}")
            return None

    def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> List[str]:
        """Search memory with multi-scope support."""
        if not self._memory:
            return []

        try:
            # Mem0 v1.0+ supports user_id, agent_id, session_id natively
            results = self._memory.search(
                query,
                user_id=user_id,
                agent_id=agent_id,
                run_id=session_id
            )

            facts = []
            for m in results:
                val = None
                if isinstance(m, dict):
                    val = m.get("memory")
                elif hasattr(m, "memory"):
                    val = getattr(m, "memory")
                if val:
                    facts.append(str(val))
            return facts
        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return []

    def add(
        self,
        text: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> None:
        """Add to memory with multi-scope support."""
        if not self._memory:
            return

        try:
            self._memory.add(
                text,
                user_id=user_id,
                agent_id=agent_id,
                run_id=session_id
            )

            # Extract to graph
            self._graph.extract_and_store(text)
        except Exception as e:
            logger.error(f"Memory add failed: {e}")
