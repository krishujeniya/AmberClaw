"""PostgreSQL database engine and session initialization using SQLAlchemy."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from loguru import logger

from amberclaw.config.schema import settings

# Global holders for database connection structures
_engine = None
_sessionmaker = None


class Base(DeclarativeBase):
    """Declarative Base class for all PostgreSQL ORM schemas."""

    pass


def init_postgres() -> bool:
    """Initializes the async PostgreSQL connection pool if configured.

    Returns:
        True if successfully configured and initialized, False otherwise.
    """
    global _engine, _sessionmaker
    url = settings.database.url
    if not url:
        logger.debug("PostgreSQL not configured (url is missing). Falling back to local storage.")
        return False

    try:
        # Normalize connection URL to use asyncpg
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

        _engine = create_async_engine(
            url,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow,
            echo=False,
        )
        _sessionmaker = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        logger.info("PostgreSQL database connection pool successfully initialized.")
        return True
    except Exception as e:
        logger.error("Failed to initialize PostgreSQL connection: {}", e)
        return False


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yields a database session instance from the connection pool."""
    if _sessionmaker is None:
        raise RuntimeError("PostgreSQL database engine is not initialized.")

    async with _sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_tables() -> None:
    """Creates all database tables defined on DeclarativeBase."""
    if _engine is not None:
        try:
            async with _engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("PostgreSQL schema tables checked and synchronized.")
        except Exception as e:
            logger.error("Error creating database tables: {}", e)
