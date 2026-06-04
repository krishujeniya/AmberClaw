# ruff: noqa: DTZ003, PLR0913, S608
"""SQLite Session Database for AmberClaw.

Stores conversation history with WAL mode enabled and provides Full-Text Search
(FTS5) capabilities over turn content.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


class SessionDB:
    """SQLite-backed conversation session log with FTS5 search."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        self._init_db()

    def _init_db(self) -> None:
        """Enable WAL mode, foreign keys, and set up database schema and triggers."""
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
                    self.conn.execute(f"ALTER TABLE session_turns ADD COLUMN {col} TEXT;")

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
        """Search across conversation turns matching the query and scope boundaries."""
        try:
            params: list[Any] = [query]
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

    def update_turn_content(self, turn_id: int, content: str) -> bool:
        """Update the content of a specific turn."""
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

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()
