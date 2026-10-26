# ruff: noqa: DTZ003, PLR0913, S608
"""SQLite Session Database for AmberClaw.

Stores conversation history with WAL mode enabled and provides Full-Text Search
(FTS5) capabilities over turn content.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


class SessionDB:
    """SQLite-backed conversation session log with FTS5 search."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or Path("data/sessions.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with self._lock:
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self._init_db()

    def _init_db(self) -> None:
        """Enable WAL mode, foreign keys, and set up database schema and triggers."""
        with self._lock:
            try:
                # Enable WAL journal mode
                self.conn.execute("PRAGMA journal_mode=WAL;")
                self.conn.execute("PRAGMA foreign_keys=ON;")

                # Table for session turns
                self.conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS session_turns (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        turn_index INTEGER NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        metadata TEXT,
                        user_id TEXT,
                        agent_id TEXT,
                        org_id TEXT,
                        UNIQUE(session_id, turn_index)
                    );
                    """,
                )

                # Ensure columns exist in case of upgrading an older DB file
                cursor = self.conn.execute("PRAGMA table_info(session_turns);")
                columns = {row["name"] for row in cursor.fetchall()}
                for col in ["user_id", "agent_id", "org_id"]:
                    if col not in columns:
                        self.conn.execute(
                            f"ALTER TABLE session_turns ADD COLUMN {col} TEXT;"
                        )

                # Virtual table for Full-Text Search (FTS5)
                self.conn.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS session_turns_fts USING fts5(
                        turn_id UNINDEXED,
                        session_id,
                        role,
                        content
                    );
                    """,
                )

                # Setup triggers to keep FTS5 virtual table synchronized
                self.conn.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS after_turn_insert
                    AFTER INSERT ON session_turns
                    BEGIN
                        INSERT INTO session_turns_fts (turn_id, session_id, role, content)
                        VALUES (new.id, new.session_id, new.role, new.content);
                    END;
                    """,
                )

                self.conn.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS after_turn_update
                    AFTER UPDATE ON session_turns
                    BEGIN
                        UPDATE session_turns_fts
                        SET content = new.content
                        WHERE turn_id = old.id;
                    END;
                    """,
                )

                self.conn.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS after_turn_delete
                    AFTER DELETE ON session_turns
                    BEGIN
                        DELETE FROM session_turns_fts WHERE turn_id = old.id;
                    END;
                    """,
                )

                self.conn.commit()
                logger.info(f"Initialized SQLite Session DB at {self.db_path}")
            except Exception as e:
                logger.error(f"Failed to initialize SQLite database: {e}")
                raise

    def add_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        turn_index: int | None = None,
        metadata: dict[str, Any] | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        org_id: str | None = None,
    ) -> int:
        """Add a conversation turn to the database.

        If turn_index is not provided, it is automatically calculated.
        """
        now = datetime.utcnow().isoformat()
        metadata_str = json.dumps(metadata) if metadata else "{}"

        with self._lock:
            try:
                if turn_index is None:
                    # Find current max turn_index for this session
                    cursor = self.conn.execute(
                        "SELECT MAX(turn_index) FROM session_turns WHERE session_id = ?;",
                        (session_id,),
                    )
                    row = cursor.fetchone()
                    current_max = row[0] if row and row[0] is not None else -1
                    turn_index = current_max + 1

                cursor = self.conn.execute(
                    """
                    INSERT INTO session_turns (
                        session_id, turn_index, role, content, timestamp, metadata, user_id, agent_id, org_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        session_id,
                        turn_index,
                        role,
                        content,
                        now,
                        metadata_str,
                        user_id,
                        agent_id,
                        org_id,
                    ),
                )
                self.conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError as e:
                logger.error(f"Integrity error adding turn: {e}")
                self.conn.rollback()
                raise
            except Exception as e:
                logger.error(f"Error adding turn to session database: {e}")
                self.conn.rollback()
                raise

    def get_turns(
        self,
        session_id: str | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        org_id: str | None = None,
        hierarchical: bool = False,
    ) -> list[dict[str, Any]]:
        """Retrieve all turns matching the specified scope boundaries ordered by timestamp."""
        with self._lock:
            try:
                query_parts = []
                params = []
                if session_id is not None:
                    query_parts.append("session_id = ?")
                    params.append(session_id)
                if user_id is not None:
                    query_parts.append("user_id = ?")
                    params.append(user_id)
                if agent_id is not None:
                    query_parts.append("agent_id = ?")
                    params.append(agent_id)
                if org_id is not None:
                    query_parts.append("org_id = ?")
                    params.append(org_id)

                connector = " OR " if hierarchical else " AND "
                where_clause = connector.join(query_parts) if query_parts else "1=1"
                sql = f"""
                    SELECT id, session_id, turn_index, role, content, timestamp, metadata, user_id, agent_id, org_id
                    FROM session_turns
                    WHERE {where_clause}
                    ORDER BY turn_index ASC;
                """
                cursor = self.conn.execute(sql, tuple(params))
                turns = []
                for row in cursor.fetchall():
                    turns.append(
                        {
                            "id": row["id"],
                            "session_id": row["session_id"],
                            "turn_index": row["turn_index"],
                            "role": row["role"],
                            "content": row["content"],
                            "timestamp": row["timestamp"],
                            "metadata": json.loads(row["metadata"] or "{}"),
                            "user_id": row["user_id"],
                            "agent_id": row["agent_id"],
                            "org_id": row["org_id"],
                        },
                    )
                return turns
            except Exception as e:
                logger.error(f"Failed to fetch turns: {e}")
                return []

    def search_turns(
        self,
        query: str,
        session_id: str | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        org_id: str | None = None,
        hierarchical: bool = False,
    ) -> list[dict[str, Any]]:
        with self._lock:
            try:
                # Sanitize query for SQLite FTS5 string matching
                safe_query = query.strip()
                if safe_query and not (
                    safe_query.startswith('"') and safe_query.endswith('"')
                ):
                    safe_query = f'"{safe_query.replace(chr(34), chr(34) + chr(34))}"'

                params: list[Any] = [safe_query]
                scope_parts = []
                if session_id is not None:
                    scope_parts.append("t.session_id = ?")
                    params.append(session_id)
                if user_id is not None:
                    scope_parts.append("t.user_id = ?")
                    params.append(user_id)
                if agent_id is not None:
                    scope_parts.append("t.agent_id = ?")
                    params.append(agent_id)
                if org_id is not None:
                    scope_parts.append("t.org_id = ?")
                    params.append(org_id)

                if scope_parts:
                    connector = " OR " if hierarchical else " AND "
                    scope_clause = f"({connector.join(scope_parts)})"
                    where_clause = f"f.content MATCH ? AND {scope_clause}"
                else:
                    where_clause = "f.content MATCH ?"

                sql = f"""
                    SELECT t.id, t.session_id, t.turn_index, t.role, t.content, t.timestamp, t.metadata, t.user_id, t.agent_id, t.org_id
                    FROM session_turns t
                    JOIN session_turns_fts f ON t.id = f.turn_id
                    WHERE {where_clause}
                    ORDER BY t.timestamp DESC;
                """
                cursor = self.conn.execute(sql, tuple(params))
                results = []
                for row in cursor.fetchall():
                    results.append(
                        {
                            "id": row["id"],
                            "session_id": row["session_id"],
                            "turn_index": row["turn_index"],
                            "role": row["role"],
                            "content": row["content"],
                            "timestamp": row["timestamp"],
                            "metadata": json.loads(row["metadata"] or "{}"),
                            "user_id": row["user_id"],
                            "agent_id": row["agent_id"],
                            "org_id": row["org_id"],
                        },
                    )
                return results
            except Exception as e:
                logger.error(f"Failed to search turns with query '{query}': {e}")
                return []

    def delete_turn(self, turn_id: int) -> bool:
        """Delete a specific turn from the database."""
        with self._lock:
            try:
                self.conn.execute(
                    "DELETE FROM session_turns WHERE id = ?;",
                    (turn_id,),
                )
                self.conn.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to delete turn {turn_id}: {e}")
                self.conn.rollback()
                return False

    def delete_session(self, session_id: str) -> int:
        """Delete all turns for a specific session ID (returns deleted count)."""
        with self._lock:
            try:
                cursor = self.conn.execute(
                    "DELETE FROM session_turns WHERE session_id = ?;",
                    (session_id,),
                )
                deleted_count = cursor.rowcount
                self.conn.execute(
                    "DELETE FROM session_turns_fts WHERE session_id = ?;",
                    (session_id,),
                )
                self.conn.commit()
                return deleted_count
            except Exception as e:
                logger.error(f"Failed to delete session {session_id}: {e}")
                self.conn.rollback()
                return 0

    def purge_all_sessions(self) -> int:
        """Purge all stored session turns (returns deleted count)."""
        with self._lock:
            try:
                cursor = self.conn.execute("DELETE FROM session_turns;")
                deleted_count = cursor.rowcount
                self.conn.execute("DELETE FROM session_turns_fts;")
                self.conn.commit()
                return deleted_count
            except Exception as e:
                logger.error(f"Failed to purge all sessions: {e}")
                self.conn.rollback()
                return 0

    def update_turn_content(self, turn_id: int, content: str) -> bool:
        """Update the content of a specific turn."""
        with self._lock:
            try:
                self.conn.execute(
                    "UPDATE session_turns SET content = ? WHERE id = ?;",
                    (content, turn_id),
                )
                self.conn.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to update turn {turn_id} content: {e}")
                self.conn.rollback()
                return False

    def export_user_data(
        self,
        user_id: str | None = None,
        session_id: str | None = None,
        org_id: str | None = None,
    ) -> dict[str, Any]:
        """Export session data in machine-readable format with SHA-256 integrity verification (GDPR Art. 15 & 20)."""
        turns = self.get_turns(session_id=session_id, user_id=user_id, org_id=org_id)
        canonical_content = json.dumps(turns, sort_keys=True).encode("utf-8")
        checksum = hashlib.sha256(canonical_content).hexdigest()

        return {
            "export_id": f"gdpr_exp_{uuid.uuid4().hex[:12]}",
            "exported_at": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "session_id": session_id,
            "org_id": org_id,
            "schema_version": "2026.1.0",
            "total_turns": len(turns),
            "turns": turns,
            "checksum_sha256": checksum,
        }

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            self.conn.close()

    # ---------------------------------------------------------------------------
    # Async Non-Blocking APIs (dispatched to threadpool to avoid event loop stalls)
    # ---------------------------------------------------------------------------

    async def aadd_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        org_id: str | None = None,
    ) -> int | None:
        """Asynchronously append a turn to session history."""
        return await asyncio.to_thread(
            self.add_turn,
            session_id=session_id,
            role=role,
            content=content,
            metadata=metadata,
            user_id=user_id,
            agent_id=agent_id,
            org_id=org_id,
        )

    async def aget_turns(
        self,
        session_id: str | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        org_id: str | None = None,
        hierarchical: bool = False,
    ) -> list[dict[str, Any]]:
        """Asynchronously retrieve turns matching scope boundaries."""
        return await asyncio.to_thread(
            self.get_turns,
            session_id=session_id,
            user_id=user_id,
            agent_id=agent_id,
            org_id=org_id,
            hierarchical=hierarchical,
        )

    async def asearch_turns(
        self,
        query: str,
        session_id: str | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        org_id: str | None = None,
        hierarchical: bool = True,
    ) -> list[dict[str, Any]]:
        """Asynchronously perform FTS5 search across session turns."""
        return await asyncio.to_thread(
            self.search_turns,
            query=query,
            session_id=session_id,
            user_id=user_id,
            agent_id=agent_id,
            org_id=org_id,
            hierarchical=hierarchical,
        )

    async def adelete_session(self, session_id: str) -> int:
        """Asynchronously delete all turns for a session."""
        return await asyncio.to_thread(self.delete_session, session_id)

    async def apurge_all_sessions(self) -> int:
        """Asynchronously purge all session turns."""
        return await asyncio.to_thread(self.purge_all_sessions)

    async def aexport_user_data(
        self,
        user_id: str | None = None,
        session_id: str | None = None,
        org_id: str | None = None,
    ) -> dict[str, Any]:
        """Asynchronously export user data for GDPR portability."""
        return await asyncio.to_thread(
            self.export_user_data,
            user_id=user_id,
            session_id=session_id,
            org_id=org_id,
        )

    async def aclose(self) -> None:
        """Asynchronously close database connection."""
        await asyncio.to_thread(self.close)
