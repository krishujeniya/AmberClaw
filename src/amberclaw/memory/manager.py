import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone

try:
    from mem0 import MemoryClient
except ImportError:
    MemoryClient = None

logger = logging.getLogger(__name__)

class MemoryRecord(BaseModel):
    """
    Standardized memory record format for the OS.
    """
    id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class MemoryManager:
    """
    The 3-Layer Memory System for AmberClaw AI OS.
    Integrates Mem0 and ChromaDB for cross-session, user-specific, and global RAG persistence.
    """
    def __init__(self, use_mem0: bool = True):
        self._client = None
        
        if use_mem0 and MemoryClient:
            # Initialize the mem0 client (assumes MEM0_API_KEY is in environment)
            try:
                self._client = MemoryClient()
                logger.info("Initialized Mem0 MemoryClient.")
            except Exception as e:
                logger.warning(f"Could not initialize Mem0 Client (missing API key?): {e}")
        elif use_mem0:
            logger.warning("mem0ai is not installed. Falling back to in-memory mode.")
            
        # In a full implementation, we'd also initialize ChromaDB for custom RAG collections here
        self._local_cache: List[MemoryRecord] = []

    async def add_memory(self, content: str, user_id: str, agent_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Store a new memory fact or interaction.
        """
        logger.info(f"Adding memory for user {user_id}")
        if self._client:
            # Mem0 API call
            meta = metadata or {}
            if agent_id:
                meta["agent_id"] = agent_id
            response = self._client.add(messages=[{"role": "user", "content": content}], user_id=user_id, metadata=meta)
            # Response handling varies by version; returning a dummy ID for now
            return "mem0_" + str(hash(content))
            
        else:
            # Local fallback
            record = MemoryRecord(
                id=f"loc_{len(self._local_cache)}",
                content=content,
                metadata=metadata or {}
            )
            self._local_cache.append(record)
            return record.id

    async def search_memory(self, query: str, user_id: str, limit: int = 5) -> List[MemoryRecord]:
        """
        Retrieve relevant memories based on a semantic query.
        """
        logger.info(f"Searching memory for user {user_id} with query: {query}")
        results = []
        if self._client:
            try:
                memories = self._client.search(query=query, user_id=user_id, limit=limit)
                for mem in memories:
                    # Map the raw output into our standard MemoryRecord
                    results.append(
                        MemoryRecord(
                            id=mem.get("id", "unknown"),
                            content=mem.get("memory", mem.get("content", "")),
                            metadata=mem.get("metadata", {})
                        )
                    )
            except Exception as e:
                logger.error(f"Error searching Mem0: {e}")
        else:
            # Basic fallback: exact text match
            results = [m for m in self._local_cache if query.lower() in m.content.lower()][:limit]
            
        return results

    async def clear_memory(self, user_id: str) -> bool:
        """
        Delete all memories for a specific user.
        """
        if self._client:
            try:
                self._client.delete_all(user_id=user_id)
                return True
            except Exception as e:
                logger.error(f"Error clearing Mem0 memory: {e}")
                return False
        else:
            self._local_cache = [m for m in self._local_cache if m.metadata.get("user_id") != user_id]
            return True
