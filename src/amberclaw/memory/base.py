# ruff: noqa: UP042
"""
AmberClaw Memory Base Interface
"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel

from amberclaw.models.message import Message


class MemoryScope(str, Enum):
    """Supported memory access scopes."""
    USER = "user"
    AGENT = "agent"
    SESSION = "session"
    ORGANIZATION = "organization"


class ScopeContext(BaseModel):
    """Context defining multi-scope boundaries for memory access."""
    user_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    org_id: str | None = None


class MemoryLayer(BaseModel):
    """Metadata about a memory layer."""
    name: str
    description: str
    is_persistent: bool


class BaseMemory(ABC):
    """Abstract base class for all memory providers."""
    
    @abstractmethod
    async def store(self, key: str, data: Any, metadata: dict[str, Any] | None = None):
        """Store data in memory."""
        pass

    @abstractmethod
    async def retrieve(self, key: str) -> Any | None:
        """Retrieve data from memory."""
        pass

    @abstractmethod
    async def search(self, query: str, limit: int = 5) -> list[Any]:
        """Search memory semantically."""
        pass


class MemoryManager:
    """Orchestrates the 3-layer memory system."""
    
    def __init__(self):
        self.short_term: list[Message] = []  # In-memory context
        self.long_term: BaseMemory | None = None  # Vector/Database
        self.frozen: BaseMemory | None = None     # Read-only knowledge
    
    async def add_to_context(self, message: Message):
        """Add a message to the short-term context."""
        self.short_term.append(message)
        # Handle context window compression if needed
        
    async def commit_to_long_term(self, session_id: str):
        """Commit current context to long-term storage."""
        if self.long_term:
            await self.long_term.store(session_id, self.short_term)
