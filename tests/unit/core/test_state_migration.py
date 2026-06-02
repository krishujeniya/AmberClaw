"""Unit tests for PostgreSQL and Redis state migration and messaging fallbacks."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from amberclaw.bus.events import InboundMessage
from amberclaw.bus.queue import MessageBus
from amberclaw.config.schema import settings
from amberclaw.database import init_postgres, init_redis
from amberclaw.session.manager import Session, SessionManager


def test_db_redis_initialization_defaults() -> None:
    """Verify that PostgreSQL and Redis return False when config is empty."""
    # Reset config temporarily to empty urls
    with patch.object(settings.database, "url", None), patch.object(settings.redis, "url", None):
        assert init_postgres() is False
        assert init_redis() is False


def test_session_manager_jsonl_fallback(tmp_path: Path) -> None:
    """Verify that SessionManager falls back to JSONL when Postgres/Redis are unconfigured."""
    with patch.object(settings.database, "url", None), patch.object(settings.redis, "url", None):
        manager = SessionManager(tmp_path)
        assert manager.db_active is False
        assert manager.redis_active is False

        # Create session
        session = Session(key="test:fallback")
        session.add_message("user", "Hello world")
        manager.save(session)

        # Check local path existence
        expected_path = tmp_path / "sessions" / "test_fallback.jsonl"
        assert expected_path.exists()

        # Load back
        loaded = manager.get_or_create("test:fallback")
        assert len(loaded.messages) == 1
        assert loaded.messages[0]["content"] == "Hello world"


@pytest.mark.asyncio
async def test_session_manager_postgresql_active(tmp_path: Path) -> None:
    """Verify SessionManager interacts with PostgreSQL mock backend when active."""
    # Mock postgres initialization
    mock_db_session = MagicMock()
    mock_execute = AsyncMock()
    mock_db_session.execute = mock_execute
    mock_db_session.commit = AsyncMock()
    mock_db_session.rollback = AsyncMock()

    # Stub get_db_session generator
    async def fake_get_db_session():
        yield mock_db_session

    with patch("amberclaw.session.manager.init_postgres", return_value=True), \
         patch("amberclaw.session.manager.create_tables", return_value=None), \
         patch("amberclaw.session.manager.init_redis", return_value=False), \
         patch("amberclaw.database.postgres.get_db_session", side_effect=fake_get_db_session):

        # Setup database mock models returning a result
        mock_result = MagicMock()
        mock_scalar = MagicMock(key="test:postgres", messages=[{"role": "user", "content": "from postgres"}],
                                created_at=None, updated_at=None, metadata_json={}, last_consolidated=0)
        mock_result.scalar_one_or_none.return_value = mock_scalar
        mock_execute.return_value = mock_result

        manager = SessionManager(tmp_path)
        assert manager.db_active is True

        # Load should execute select query
        session = manager.get_or_create("test:postgres")
        assert session.key == "test:postgres"
        assert len(session.messages) == 1
        assert session.messages[0]["content"] == "from postgres"


@pytest.mark.asyncio
async def test_session_manager_redis_cache(tmp_path: Path) -> None:
    """Verify session caching in Redis is invoked when Redis is configured."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = json.dumps({
        "key": "test:redis",
        "messages": [{"role": "assistant", "content": "from redis cache"}],
        "created_at": "2026-06-02T12:00:00",
        "updated_at": "2026-06-02T12:00:00",
        "metadata": {},
        "last_consolidated": 0,
    })

    with patch("amberclaw.session.manager.init_postgres", return_value=False), \
         patch("amberclaw.session.manager.init_redis", return_value=True), \
         patch("amberclaw.session.manager.get_redis", return_value=mock_redis):

        manager = SessionManager(tmp_path)
        assert manager.redis_active is True

        session = manager.get_or_create("test:redis")
        assert session.key == "test:redis"
        assert len(session.messages) == 1
        assert session.messages[0]["content"] == "from redis cache"


@pytest.mark.asyncio
async def test_message_bus_redis_pubsub() -> None:
    """Verify that MessageBus publishes to Redis when client is active."""
    mock_redis = AsyncMock()
    
    with patch("amberclaw.bus.queue.get_redis", return_value=mock_redis):
        bus = MessageBus()
        msg = InboundMessage(channel="cli", sender_id="user", chat_id="direct", content="hello")
        
        await bus.publish_inbound(msg)
        
        # Redis publish should be called
        mock_redis.publish.assert_called_once()
        args, kwargs = mock_redis.publish.call_args
        assert args[0] == "amberclaw_inbound"
        assert "hello" in args[1]
