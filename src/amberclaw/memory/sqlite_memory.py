"""SQLite-backed Session Memory Manager for AmberClaw.

Provides persistent conversation history, turn tracking, and FTS5 full-text search.
"""

from pathlib import Path
from typing import Any, Optional

from amberclaw.memory.session_db import SessionDB


class SQLiteMemoryManager:
    """High-level memory manager interfacing with SQLite SessionDB."""

    def __init__(self, db_path: str | Path = "data/sessions.db"):
        self.db_path = Path(db_path)
        self.session_db = SessionDB(self.db_path)

    def save_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        org_id: Optional[str] = None,
    ) -> int:
        """Save a conversation turn to persistent SQLite storage."""
        return self.session_db.add_turn(
            session_id=session_id,
            role=role,
            content=content,
            metadata=metadata,
            user_id=user_id,
            agent_id=agent_id,
            org_id=org_id,
        )

    def get_history(
        self,
        session_id: str,
        limit: Optional[int] = 50,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Retrieve conversation history for a given session."""
        turns = self.session_db.get_turns(
            session_id=session_id,
            user_id=user_id,
            agent_id=agent_id,
        )
        if limit and len(turns) > limit:
            return turns[-limit:]
        return turns

    def search_history(
        self,
        query: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Perform full-text search (FTS5) over stored conversation turns."""
        return self.session_db.search_turns(
            query=query,
            session_id=session_id,
            user_id=user_id,
        )

    def delete_turn(self, turn_id: int) -> bool:
        """Delete a specific conversation turn by ID."""
        return self.session_db.delete_turn(turn_id)

    def close(self) -> None:
        """Close the underlying SQLite database connection."""
        self.session_db.close()
