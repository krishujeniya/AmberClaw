import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class KnowledgeEntry(BaseModel):
    """A piece of stored knowledge."""

    id: Optional[int] = None
    category: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class KnowledgeStore:
    """Manages long-term knowledge storage using SQLite."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            # FTS for search
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts 
                USING fts5(category, content, content='knowledge', content_rowid='id')
            """)
            # Triggers to keep FTS in sync
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS knowledge_ai AFTER INSERT ON knowledge BEGIN
                    INSERT INTO knowledge_fts(rowid, category, content) VALUES (new.id, new.category, new.content);
                END;
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS knowledge_ad AFTER DELETE ON knowledge BEGIN
                    INSERT INTO knowledge_fts(knowledge_fts, rowid, category, content) VALUES('delete', old.id, old.category, old.content);
                END;
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS knowledge_au AFTER UPDATE ON knowledge BEGIN
                    INSERT INTO knowledge_fts(knowledge_fts, rowid, category, content) VALUES('delete', old.id, old.category, old.content);
                    INSERT INTO knowledge_fts(rowid, category, content) VALUES (new.id, new.category, new.content);
                END;
            """)

    def add(self, category: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> int:
        """Add a new knowledge entry."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO knowledge (category, content, metadata, created_at) VALUES (?, ?, ?, ?)",
                (category, content, json.dumps(metadata or {}), datetime.now().isoformat()),
            )
            return int(cursor.lastrowid or 0)

    def search(self, query: str, limit: int = 5) -> List[KnowledgeEntry]:
        """Search knowledge base using FTS."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT k.id, k.category, k.content, k.metadata, k.created_at
                FROM knowledge k
                JOIN knowledge_fts f ON k.id = f.rowid
                WHERE knowledge_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """,
                (query, limit),
            )

            return [
                KnowledgeEntry(
                    id=row["id"],
                    category=row["category"],
                    content=row["content"],
                    metadata=json.loads(row["metadata"]),
                    created_at=row["created_at"],
                )
                for row in cursor.fetchall()
            ]

    def list_categories(self) -> List[str]:
        """List all distinctive categories."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT DISTINCT category FROM knowledge")
            return [row[0] for row in cursor.fetchall()]

    def delete(self, entry_id: int) -> None:
        """Delete an entry by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM knowledge WHERE id = ?", (entry_id,))
