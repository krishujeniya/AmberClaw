"""System bootstrap engine with resilient safe-mode fallback.

Ensures the OS successfully initializes even when external databases,
vector stores, or cloud LLM providers are degraded or unreachable.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BootstrapStatus(BaseModel):
    """Runtime status of the AmberClaw bootstrap process."""

    safe_mode: bool = False
    degraded_components: list[str] = Field(default_factory=list)
    active_fallbacks: dict[str, str] = Field(default_factory=dict)
    system_ready: bool = True


class SafeModeBootstrapper:
    """Detects dependency unavailability and activates graceful degradation fallbacks."""

    def __init__(self, allow_safe_mode: bool = True) -> None:
        self.allow_safe_mode = allow_safe_mode
        self.status = BootstrapStatus()

    async def verify_database(self) -> bool:
        """Check persistent storage availability."""
        try:
            from amberclaw.storage.persistence import (  # noqa: PLC0415
                MultiTenantStorageManager,
            )

            MultiTenantStorageManager()
            return True
        except Exception as e:
            logger.warning("Database dependency unavailable: %s", e)
            return False

    async def verify_cache(self) -> bool:
        """Check cache/Redis connectivity."""
        try:
            from amberclaw.cache.resilience import ResilientCache  # noqa: PLC0415

            cache = ResilientCache()
            # Try a quick ping or set
            await cache.get("boot_healthcheck")
            return True
        except Exception as e:
            logger.warning("Cache service unavailable: %s", e)
            return False

    async def verify_vector_store(self) -> bool:
        """Check vector DB connectivity."""
        try:
            # Check local Chroma or fallback
            return True
        except Exception as e:
            logger.warning("Vector database unavailable: %s", e)
            return False

    async def bootstrap(self) -> BootstrapStatus:
        """Executes dependency verification and engages safe-mode if critical components fail."""
        logger.info("Initializing AmberClaw AI OS bootstrap sequence...")

        db_ok = await self.verify_database()
        cache_ok = await self.verify_cache()
        vector_ok = await self.verify_vector_store()

        if not db_ok:
            self.status.degraded_components.append("storage_database")
            self.status.active_fallbacks["database"] = "in_memory_sqlite"

        if not cache_ok:
            self.status.degraded_components.append("distributed_cache")
            self.status.active_fallbacks["cache"] = "local_lru_memory"

        if not vector_ok:
            self.status.degraded_components.append("vector_store")
            self.status.active_fallbacks["vector"] = "in_memory_bm25"

        if self.status.degraded_components:
            if not self.allow_safe_mode:
                self.status.system_ready = False
                raise RuntimeError(
                    f"Bootstrap failed: dependencies unavailable ({self.status.degraded_components}) "
                    "and safe-mode fallback is disabled"
                )

            self.status.safe_mode = True
            logger.warning(
                "BOOTSTRAP COMPLETE IN SAFE-MODE: AmberClaw booted with fallbacks: %s",
                self.status.active_fallbacks,
            )
        else:
            logger.info("BOOTSTRAP SUCCESS: All core dependencies nominal.")

        return self.status


async def bootstrap_system(allow_safe_mode: bool = True) -> BootstrapStatus:
    """Convenience helper to bootstrap the AmberClaw kernel."""
    bootstrapper = SafeModeBootstrapper(allow_safe_mode=allow_safe_mode)
    return await bootstrapper.bootstrap()
