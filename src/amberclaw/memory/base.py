"""
AmberClaw Memory Base Interface
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from amberclaw.models.message import Message, Conversation


class MemoryLayer(BaseModel):
    """Metadata about a memory layer."""
    name: str
    description: str
    is_persistent: bool


class BaseMemory(ABC):
    """Abstract base class for all memory providers."""
    
    @abstractmethod
    async def store(self, key: str, data: Any, metadata: Optional[Dict[str, Any]] = None):
        """Store data in memory."""
        pass

    @abstractmethod
    async def retrieve(self, key: str) -> Optional[Any]:
        """Retrieve data from memory."""
        pass

    @abstractmethod
    async def search(self, query: str, limit: int = 5) -> List[Any]:
        """Search memory semantically."""
        pass


class MemoryManager:
    """Orchestrates the 3-layer memory system."""
    
    def __init__(self):
        self.short_term: List[Message] = []  # In-memory context
        self.long_term: Optional[BaseMemory] = None  # Vector/Database
        self.frozen: Optional[BaseMemory] = None     # Read-only knowledge
    
    async def add_to_context(self, message: Message):
        """Add a message to the short-term context."""
        self.short_term.append(message)
        # Handle context window compression if needed
        
    async def commit_to_long_term(self, session_id: str):
        """Commit current context to long-term storage."""
        if self.long_term:
            await self.long_term.store(session_id, self.short_term)
