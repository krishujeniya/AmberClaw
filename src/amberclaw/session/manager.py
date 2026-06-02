"""Session management for conversation history with optional PostgreSQL and Redis support."""

import asyncio
import json
import shutil
import threading
from collections.abc import Coroutine
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

from loguru import logger
from sqlalchemy import Column, DateTime, Integer, JSON, String
from sqlalchemy.future import select

from amberclaw.config.paths import get_legacy_sessions_dir
from amberclaw.database.postgres import Base, create_tables, init_postgres
from amberclaw.database.redis_client import get_redis, init_redis
from amberclaw.utils.helpers import ensure_dir, safe_filename

T = TypeVar("T")


def run_async_as_sync(coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine synchronously.

    Safe to call even if an event loop is currently running on the active thread
    since it delegates execution to a new loop within a background thread.
    """
    result: list[Any] = [None]
    exception: list[Exception | None] = [None]

    def target() -> None:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result[0] = loop.run_until_complete(coro)
        except Exception as e:
            exception[0] = e
        finally:
            loop.close()

    thread = threading.Thread(target=target)
    thread.start()
    thread.join()

    if exception[0] is not None:
        raise exception[0]
    return result[0]


class DBSessionModel(Base):
    """SQLAlchemy model for conversation sessions in PostgreSQL."""

    __tablename__ = "amberclaw_sessions"

    key = Column(String(255), primary_key=True)
    messages = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata_json = Column(JSON, default=dict)
    last_consolidated = Column(Integer, default=0)


@dataclass
class Session:
    """A conversation session.

    Stores messages in JSONL format for easy reading and persistence.

    Important: Messages are append-only for LLM cache efficiency.
    The consolidation process writes summaries to MEMORY.md/HISTORY.md
    but does NOT modify the messages list or get_history() output.
    """

    key: str  # channel:chat_id
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    last_consolidated: int = 0  # Number of messages already consolidated to files

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to the session."""
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs,
        }
        self.messages.append(msg)
        self.updated_at = datetime.now()

    def get_history(self, max_messages: int = 500) -> list[dict[str, Any]]:
        """Return unconsolidated messages for LLM input, aligned to a user turn."""
        unconsolidated = self.messages[self.last_consolidated :]
        sliced = unconsolidated[-max_messages:]

        # Drop leading non-user messages to avoid orphaned tool_result blocks
        for i, m in enumerate(sliced):
            if m.get("role") == "user":
                sliced = sliced[i:]
                break

        out: list[dict[str, Any]] = []
        for m in sliced:
            entry: dict[str, Any] = {
                "role": m["role"],
                "content": m.get("content", ""),
            }
            for k in ("tool_calls", "tool_call_id", "name"):
                if k in m:
                    entry[k] = m[k]
            out.append(entry)
        return out

    def clear(self) -> None:
        """Clear all messages and reset session to initial state."""
        self.messages = []
        self.last_consolidated = 0
        self.updated_at = datetime.now()


class SessionManager:
    """Manages conversation sessions.

    Supports PostgreSQL storage and Redis caching when configured,
    with local JSONL fallback.
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.sessions_dir = ensure_dir(self.workspace / "sessions")
        self.legacy_sessions_dir = get_legacy_sessions_dir()
        self._cache: dict[str, Session] = {}

        # Initialize PostgreSQL & Redis if configured
        self.db_active = init_postgres()
        self.redis_active = init_redis()

        if self.db_active:
            try:
                run_async_as_sync(create_tables())
                logger.info("Session PostgreSQL tables verified.")
            except Exception as e:
                logger.error("Failed to initialize PostgreSQL session tables: {}. Falling back.", e)
                self.db_active = False

    def _get_session_path(self, key: str) -> Path:
        """Get the file path for a session."""
        safe_key = safe_filename(key.replace(":", "_"))
        return self.sessions_dir / f"{safe_key}.jsonl"

    def _get_legacy_session_path(self, key: str) -> Path:
        """Legacy global session path (~/.amberclaw/sessions/)."""
        safe_key = safe_filename(key.replace(":", "_"))
        return self.legacy_sessions_dir / f"{safe_key}.jsonl"

    def get_or_create(self, key: str) -> Session:
        """Get an existing session or create a new one.

        Args:
            key: Session key (usually channel:chat_id).

        Returns:
            The session.
        """
        if key in self._cache:
            return self._cache[key]

        # 1. Try Redis cache if active
        if self.redis_active:
            cached = self._redis_load(key)
            if cached:
                self._cache[key] = cached
                return cached

        # 2. Load from Postgres or JSONL
        session = self._load(key)
        if session is None:
            session = Session(key=key)

        self._cache[key] = session
        return session

    def _redis_save(self, session: Session) -> None:
        """Cache the session in Redis with a 24-hour expiration."""
        client = get_redis()
        if not client:
            return

        async def _save():
            data = {
                "key": session.key,
                "messages": session.messages,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "metadata": session.metadata,
                "last_consolidated": session.last_consolidated,
            }
            await client.setex(
                f"session_cache:{session.key}",
                86400,
                json.dumps(data, ensure_ascii=False),
            )

        try:
            run_async_as_sync(_save())
        except Exception as e:
            logger.warning("Failed to cache session in Redis: {}", e)

    def _redis_load(self, key: str) -> Session | None:
        """Load session from Redis cache."""
        client = get_redis()
        if not client:
            return None

        async def _load():
            val = await client.get(f"session_cache:{key}")
            if val:
                data = json.loads(val)
                return Session(
                    key=data["key"],
                    messages=data["messages"],
                    created_at=datetime.fromisoformat(data["created_at"]),
                    updated_at=datetime.fromisoformat(data["updated_at"]),
                    metadata=data["metadata"],
                    last_consolidated=data["last_consolidated"],
                )
            return None

        try:
            return run_async_as_sync(_load())
        except Exception as e:
            logger.warning("Failed to load cached session from Redis: {}", e)
            return None

    def _load(self, key: str) -> Session | None:
        """Load a session from database or disk."""
        if self.db_active:
            from amberclaw.database.postgres import get_db_session

            async def _load_db():
                async for db_sess in get_db_session():
                    stmt = select(DBSessionModel).where(DBSessionModel.key == key)
                    res = await db_sess.execute(stmt)
                    item = res.scalar_one_or_none()
                    if item:
                        return Session(
                            key=item.key,
                            messages=item.messages or [],
                            created_at=item.created_at,
                            updated_at=item.updated_at,
                            metadata=item.metadata_json or {},
                            last_consolidated=item.last_consolidated,
                        )
                return None

            try:
                db_result = run_async_as_sync(_load_db())
                if db_result:
                    return db_result
            except Exception as e:
                logger.error("Failed to load session {} from PostgreSQL: {}", key, e)

        # Fallback to local files
        path = self._get_session_path(key)
        if not path.exists():
            legacy_path = self._get_legacy_session_path(key)
            if legacy_path.exists():
                try:
                    shutil.move(str(legacy_path), str(path))
                    logger.info("Migrated session {} from legacy path", key)
                except Exception:
                    logger.exception("Failed to migrate session {}", key)

        if not path.exists():
            return None

        try:
            messages = []
            metadata = {}
            created_at = None
            last_consolidated = 0

            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    data = json.loads(line)

                    if data.get("_type") == "metadata":
                        metadata = data.get("metadata", {})
                        created_at = (
                            datetime.fromisoformat(data["created_at"])
                            if data.get("created_at")
                            else None
                        )
                        last_consolidated = data.get("last_consolidated", 0)
                    else:
                        messages.append(data)

            return Session(
                key=key,
                messages=messages,
                created_at=created_at or datetime.now(),
                metadata=metadata,
                last_consolidated=last_consolidated,
            )
        except Exception as e:
            logger.warning("Failed to load session {}: {}", key, e)
            return None

    def save(self, session: Session) -> None:
        """Save a session to database/disk and Redis cache."""
        # 1. Update local cache
        self._cache[session.key] = session

        # 2. Update Redis cache if active
        if self.redis_active:
            self._redis_save(session)

        # 3. Save to database or JSONL
        if self.db_active:
            from amberclaw.database.postgres import get_db_session

            async def _save_db():
                async for db_sess in get_db_session():
                    stmt = select(DBSessionModel).where(DBSessionModel.key == session.key)
                    res = await db_sess.execute(stmt)
                    item = res.scalar_one_or_none()
                    if not item:
                        item = DBSessionModel(
                            key=session.key,
                            messages=session.messages,
                            created_at=session.created_at,
                            updated_at=session.updated_at,
                            metadata_json=session.metadata,
                            last_consolidated=session.last_consolidated,
                        )
                        db_sess.add(item)
                    else:
                        item.messages = session.messages
                        item.updated_at = session.updated_at
                        item.metadata_json = session.metadata
                        item.last_consolidated = session.last_consolidated
                        db_sess.add(item)
                    await db_sess.commit()

            try:
                run_async_as_sync(_save_db())
                return
            except Exception as e:
                logger.error("Failed to save session {} to PostgreSQL: {}", session.key, e)

        # Fallback to local files
        path = self._get_session_path(session.key)
        with open(path, "w", encoding="utf-8") as f:
            metadata_line = {
                "_type": "metadata",
                "key": session.key,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "metadata": session.metadata,
                "last_consolidated": session.last_consolidated,
            }
            f.write(json.dumps(metadata_line, ensure_ascii=False) + "\n")
            for msg in session.messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    def invalidate(self, key: str) -> None:
        """Remove a session from the in-memory cache and Redis."""
        self._cache.pop(key, None)
        if self.redis_active:
            client = get_redis()
            if client:
                async def _delete():
                    await client.delete(f"session_cache:{key}")
                try:
                    run_async_as_sync(_delete())
                except Exception as e:
                    logger.warning("Failed to invalidate Redis cache: {}", e)

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions.

        Returns:
            List of session info dicts.
        """
        if self.db_active:
            from amberclaw.database.postgres import get_db_session

            async def _list_db():
                async for db_sess in get_db_session():
                    stmt = select(DBSessionModel).order_by(DBSessionModel.updated_at.desc())
                    res = await db_sess.execute(stmt)
                    items = res.scalars().all()
                    return [
                        {
                            "key": item.key,
                            "created_at": item.created_at.isoformat(),
                            "updated_at": item.updated_at.isoformat(),
                            "path": "postgresql",
                        }
                        for item in items
                    ]
                return []

            try:
                return run_async_as_sync(_list_db())
            except Exception as e:
                logger.error("Failed to list sessions from PostgreSQL: {}", e)

        # Fallback to local files
        sessions = []
        for path in self.sessions_dir.glob("*.jsonl"):
            try:
                # Read just the metadata line
                with open(path, encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    if first_line:
                        data = json.loads(first_line)
                        if data.get("_type") == "metadata":
                            key = data.get("key") or path.stem.replace("_", ":", 1)
                            sessions.append(
                                {
                                    "key": key,
                                    "created_at": data.get("created_at"),
                                    "updated_at": data.get("updated_at"),
                                    "path": str(path),
                                },
                            )
            except Exception:
                continue

        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)
