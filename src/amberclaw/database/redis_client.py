"""Redis client pool and initialization helper."""

import redis.asyncio as aioredis
from loguru import logger

from amberclaw.config.schema import settings

# Global Redis client instance
_redis_client: aioredis.Redis | None = None


def init_redis() -> bool:
    """Initializes the Redis connection pool if configured.

    Returns:
        True if successfully configured and connected, False otherwise.
    """
    global _redis_client
    url = settings.redis.url
    if not url:
        logger.debug("Redis is not configured (url is missing).")
        return False

    try:
        _redis_client = aioredis.from_url(
            url,
            encoding="utf-8",
            decode_responses=True,
        )
        logger.info("Redis client successfully initialized.")
        return True
    except Exception as e:
        logger.error("Failed to initialize Redis client: {}", e)
        return False


def get_redis() -> aioredis.Redis | None:
    """Returns the global Redis client instance if initialized."""
    return _redis_client
