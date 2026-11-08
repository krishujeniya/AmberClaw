"""SQLite-backed Session Memory Manager for AmberClaw.

Provides persistent conversation history, turn tracking, and FTS5 full-text search.
"""

from pathlib import Path
from typing import Any

from amberclaw.memory.session_db import SessionDB


class SQLiteMemoryManager:
    """High-level memory manager interfacing with SQLite SessionDB."""

    def __init__(self, db_path: str | Path = "data/sessions.db") -> None:
        self.db_path = Path(db_path)
        self.session_db = SessionDB(self.db_path)

    def save_turn(  # noqa: PLR0913 - preserve public turn fields and optional multi-scope identifiers
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        org_id: str | None = None,
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
        limit: int | None = 50,
        user_id: str | None = None,
        agent_id: str | None = None,
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
        session_id: str | None = None,
        user_id: str | None = None,
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
