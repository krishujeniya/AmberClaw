"""Session persistence retains its pre-existing JSONL and SQL table contracts."""

from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as SQLSession

from amberclaw.session.manager import (
    DBSessionModel,
    Session,
    SessionManager,
    run_async_as_sync,
)


def test_sql_session_model_preserves_nullable_legacy_columns() -> None:
    engine = create_engine("sqlite://")
    DBSessionModel.__table__.create(engine)
    now = datetime.fromisoformat("2026-01-02T03:04:05")
    with SQLSession(engine) as db:
        db.add(
            DBSessionModel(
                key="cli:direct",
                messages=[{"role": "user", "content": "hello"}],
                created_at=now,
                updated_at=now,
                metadata_json={"locale": "en"},
                last_consolidated=1,
            )
        )
        db.commit()
        saved = db.scalars(select(DBSessionModel)).one()
        assert saved.messages == [{"role": "user", "content": "hello"}]
        assert saved.metadata_json == {"locale": "en"}
        assert saved.last_consolidated == 1
    assert not DBSessionModel.__table__.c.key.nullable
    assert all(
        column.nullable
        for column in DBSessionModel.__table__.columns
        if column.name != "key"
    )
    engine.dispose()


def test_local_jsonl_roundtrip(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    session = Session("cli:storage", metadata={"language": "日本語"})
    session.add_message("user", "hello")
    session.last_consolidated = 1
    manager.save(session)
    manager.invalidate(session.key)
    restored = manager.get_or_create(session.key)
    assert restored.messages == session.messages
    assert restored.metadata == session.metadata
    assert restored.last_consolidated == session.last_consolidated


def test_sync_coroutine_bridge_retains_return_type() -> None:
    async def result() -> tuple[str, int]:
        return "value", 7

    assert run_async_as_sync(result()) == ("value", 7)
