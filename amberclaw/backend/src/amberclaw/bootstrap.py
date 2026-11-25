"""Check initialized backend health and offer a usable local cache fallback.

This module does not initialize the application or replace its backend bindings.
Callers must initialize configured database/Redis clients, supply a vector probe,
and explicitly use any returned fallback resource in their consumers.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import aclosing

from pydantic import BaseModel, Field, PrivateAttr

from amberclaw.cache.resilience import ResilientCacheManager

logger = logging.getLogger(__name__)
HealthProbe = Callable[[], Awaitable[bool]]


class BootstrapStatus(BaseModel):
    """Result of this component's checks, not whole-application readiness.

    Runtime fallback objects are intentionally excluded from serialized status.
    The caller owns this result and must close its local resources when finished.
    """

    safe_mode: bool = False
    degraded_components: list[str] = Field(default_factory=list)
    active_fallbacks: dict[str, str] = Field(default_factory=dict)
    system_ready: bool = False
    _cache_fallback: ResilientCacheManager | None = PrivateAttr(default=None)

    @property
    def cache_fallback(self) -> ResilientCacheManager | None:
        """Usable local cache; consumers must explicitly select it."""
        return self._cache_fallback

    def close(self) -> None:
        """Release owned local fallback state; configured clients remain borrowed."""
        cache = self._cache_fallback
        self._cache_fallback = None
        if cache is not None:
            self.active_fallbacks.pop("cache", None)
            self.system_ready = False
            cache.clear()


class SafeModeBootstrapper:
    """Probe configured backends without claiming to rewire application consumers.

    Safe mode permits a degraded result instead of raising. Database and vector
    failures remain unready because no compatible replacement adapters exist here.
    Repeating bootstrap closes the previous result's owned fallback resources.
    """

    _PROBE_TIMEOUT_SECONDS = 5.0

    def __init__(
        self,
        allow_safe_mode: bool = True,
        *,
        database_probe: HealthProbe | None = None,
        cache_probe: HealthProbe | None = None,
        vector_probe: HealthProbe | None = None,
    ) -> None:
        self.allow_safe_mode = allow_safe_mode
        self.status = BootstrapStatus()
        self._database_probe = database_probe or self._configured_database_probe
        self._cache_probe = cache_probe or self._configured_cache_probe
        self._vector_probe = vector_probe or self._unconfigured_vector_probe

    @staticmethod
    async def _configured_database_probe() -> bool:
        """Execute a real read against the already initialized PostgreSQL pool."""
        from sqlalchemy import text  # noqa: PLC0415 - backend use is lazy

        from amberclaw.database.postgres import get_db_session  # noqa: PLC0415

        async with aclosing(get_db_session()) as sessions:
            async for session in sessions:
                result = await session.execute(text("SELECT 1"))
                value: object = result.scalar_one()
                return value == 1
        return False

    @staticmethod
    async def _configured_cache_probe() -> bool:
        """Ping the application's configured Redis client without replacing it."""
        from amberclaw.database.redis_client import get_redis  # noqa: PLC0415

        client = get_redis()
        return client is not None and bool(await client.ping())

    @staticmethod
    async def _unconfigured_vector_probe() -> bool:
        """No vector backend was supplied, so its health cannot be verified."""
        return False

    async def _run_probe(self, component: str, probe: HealthProbe) -> bool:
        try:
            return await asyncio.wait_for(probe(), timeout=self._PROBE_TIMEOUT_SECONDS)
        except Exception as exc:
            logger.warning("%s health probe failed (%s)", component, type(exc).__name__)
            return False

    async def verify_database(self) -> bool:
        """Check persistent storage with a bounded real or injected health probe."""
        return await self._run_probe("Database", self._database_probe)

    async def verify_cache(self) -> bool:
        """Check Redis connectivity; a missing key or local cache is not a ping."""
        return await self._run_probe("Cache", self._cache_probe)

    async def verify_vector_store(self) -> bool:
        """Check an explicitly supplied vector backend; absent means unavailable."""
        return await self._run_probe("Vector store", self._vector_probe)

    def _activate_cache_fallback(self) -> None:
        cache: ResilientCacheManager | None = None
        try:
            cache = ResilientCacheManager()
            cache.set("bootstrap_healthcheck", True)
            if cache.get("bootstrap_healthcheck") is not True:
                raise RuntimeError("Local cache failed its health check")
            cache.invalidate("bootstrap_healthcheck")
            self.status._cache_fallback = cache
            self.status.active_fallbacks["cache"] = "local_lru_memory"
        except Exception as exc:
            if cache is not None:
                cache.clear()
            logger.warning("Local cache fallback unavailable (%s)", type(exc).__name__)

    def close(self) -> None:
        """Close only resources owned by this bootstrap result."""
        self.status.close()

    async def bootstrap(self) -> BootstrapStatus:
        """Run backend checks; expose only verified, instantiated local fallbacks."""
        self.close()
        self.status = BootstrapStatus()
        db_ok = await self.verify_database()
        cache_ok = await self.verify_cache()
        vector_ok = await self.verify_vector_store()

        self.status.degraded_components = [
            name
            for name, healthy in (
                ("storage_database", db_ok),
                ("distributed_cache", cache_ok),
                ("vector_store", vector_ok),
            )
            if not healthy
        ]
        if self.status.degraded_components:
            if not self.allow_safe_mode:
                raise RuntimeError(
                    f"Bootstrap failed: dependencies unavailable ({self.status.degraded_components}) "
                    "and safe-mode fallback is disabled"
                )
            self.status.safe_mode = True
            if not cache_ok:
                self._activate_cache_fallback()

        self.status.system_ready = (
            db_ok and vector_ok and (cache_ok or self.status.cache_fallback is not None)
        )
        logger.info(
            "Bootstrap checks complete: ready=%s degraded=%s available local fallbacks=%s; "
            "application backend bindings are unchanged",
            self.status.system_ready,
            self.status.degraded_components,
            self.status.active_fallbacks,
        )
        return self.status


async def bootstrap_system(allow_safe_mode: bool = True) -> BootstrapStatus:
    """Return backend-check status and owned local resources; caller must close it.

    Without an injected vector probe on SafeModeBootstrapper, vector health remains
    unavailable. This convenience helper does not establish application readiness.
    """
    bootstrapper = SafeModeBootstrapper(allow_safe_mode=allow_safe_mode)
    return await bootstrapper.bootstrap()
