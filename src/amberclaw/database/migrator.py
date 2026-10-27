from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from loguru import logger
from sqlalchemy import create_engine

from amberclaw.config.schema import settings


def get_alembic_config(db_url: str | None = None) -> Config:
    """Build and return an Alembic Config object pointing to the package migrations."""
    root_dir = Path(__file__).resolve().parent.parent.parent.parent
    ini_path = root_dir / "alembic.ini"

    if ini_path.exists():
        cfg = Config(str(ini_path))
    else:
        cfg = Config()
        migrations_dir = Path(__file__).resolve().parent / "migrations"
        cfg.set_main_option("script_location", str(migrations_dir))
        cfg.set_main_option("version_locations", str(migrations_dir / "versions"))

    target_url = db_url or settings.database.url or "sqlite:///./data/amberclaw.db"
    cfg.set_main_option("sqlalchemy.url", target_url)
    return cfg


def apply_migrations(target_revision: str = "head", db_url: str | None = None) -> bool:
    """Run database schema migrations to the specified target revision.

    Args:
        target_revision: Revision tag or 'head' (default).
        db_url: Optional override database connection URL.

    Returns:
        True if migrations applied successfully, False otherwise.
    """
    try:
        cfg = get_alembic_config(db_url=db_url)
        logger.info(f"Applying database schema migrations to '{target_revision}'...")
        command.upgrade(cfg, target_revision)
        logger.info("Database schema migrations successfully applied.")
        return True
    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        return False


def rollback_migrations(
    target_revision: str = "base", db_url: str | None = None
) -> bool:
    """Rollback database schema migrations to the specified target revision.

    Args:
        target_revision: Revision tag, '-1', or 'base'.
        db_url: Optional override database connection URL.

    Returns:
        True if rollback succeeded, False otherwise.
    """
    try:
        cfg = get_alembic_config(db_url=db_url)
        logger.info(
            f"Rolling back database schema migrations to '{target_revision}'..."
        )
        command.downgrade(cfg, target_revision)
        logger.info("Database schema rollback completed.")
        return True
    except Exception as e:
        logger.error(f"Database rollback failed: {e}")
        return False


def get_current_revision(db_url: str | None = None) -> Any:
    """Get the currently applied migration revision on the target database."""
    try:
        url = db_url or settings.database.url or "sqlite:///./data/amberclaw.db"
        if "postgresql+asyncpg://" in url:
            url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
        engine = create_engine(url)
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            return ctx.get_current_revision()
    except Exception as e:
        logger.debug(f"Could not read current migration revision: {e}")
        return None
