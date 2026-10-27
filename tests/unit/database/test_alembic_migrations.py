"""Unit tests for Alembic database schema migrations."""

from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import create_engine, inspect

from amberclaw.database.migrator import (
    apply_migrations,
    get_current_revision,
    rollback_migrations,
)


def test_alembic_migration_upgrade_and_downgrade(tmp_path: Path):
    """Test full upgrade and rollback cycle on a fresh SQLite database."""
    db_file = tmp_path / "test_migration.db"
    db_url = f"sqlite:///{db_file}"

    # Initially, no tables exist
    assert get_current_revision(db_url=db_url) is None

    # Apply migration upgrade to head
    success = apply_migrations(target_revision="head", db_url=db_url)
    assert success is True

    # Verify current revision
    current_rev = get_current_revision(db_url=db_url)
    assert current_rev == "0001_initial"

    # Verify tables created
    engine = create_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    assert "agents" in tables
    assert "tickets" in tables
    assert "messages" in tables
    assert "workspaces" in tables

    # Test inserting an agent into the migrated table
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO agents (id, name, role, is_active) VALUES ('agent_001', 'Core Agent', 'assistant', 1)"
            )
        )
        result = conn.execute(
            sa.text("SELECT name FROM agents WHERE id = 'agent_001'")
        ).scalar()
        assert result == "Core Agent"

    # Test rollback downgrade to base
    rollback_success = rollback_migrations(target_revision="base", db_url=db_url)
    assert rollback_success is True

    # Verify tables dropped
    inspector_post = inspect(engine)
    tables_post = inspector_post.get_table_names()
    assert "agents" not in tables_post
    assert "tickets" not in tables_post
    assert "messages" not in tables_post
    assert "workspaces" not in tables_post
