"""Resilient Multi-Tier Cache with Invalidation and Fault-Tolerant Redis Fallback.

Ensures uninterrupted operation during Redis network partitions or outages
by automatically falling back to an in-memory L1 cache with circuit-breaker semantics.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from enum import StrEnum
from typing import Any

from loguru import logger


class CacheState(StrEnum):
    NORMAL = "normal"
    DEGRADED = "degraded"
    RECOVERING = "recovering"


class CacheEntry:
    """Internal cache entry wrapper storing value, TTL, and tag metadata."""

    def __init__(
        self,
        key: str,
        value: Any,
        ttl_seconds: float | None = None,
        tags: set[str] | None = None,
        version: int = 1,
    ):
        self.key = key
        self.value = value
        self.created_at = time.time()
        self.ttl_seconds = ttl_seconds
        self.tags = set(tags or [])
        self.version = version

    def is_expired(self, now: float | None = None) -> bool:
        if self.ttl_seconds is None:
            return False
        current_time = now if now is not None else time.time()
        return current_time - self.created_at >= self.ttl_seconds


class ResilientCacheManager:
    """Two-tier (L1 Memory + L2 Redis) cache manager with graceful degradation."""

    def __init__(
        self,
        redis_client: Any | None = None,
        max_l1_items: int = 1000,
        failure_threshold: int = 3,
        recovery_probe_interval_seconds: float = 30.0,
    ):
        self.redis_client = redis_client
        self.max_l1_items = max_l1_items
        self.failure_threshold = failure_threshold
        self.recovery_probe_interval = recovery_probe_interval_seconds

        self._l1_cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._tag_to_keys: dict[str, set[str]] = {}
        self._lock = threading.RLock()

        self.state = CacheState.NORMAL if redis_client else CacheState.DEGRADED
        self._consecutive_redis_failures = 0
        self._last_failure_time = 0.0

        # Metrics
        self.hits = 0
        self.misses = 0
        self.l1_hits = 0
        self.l2_hits = 0
        self.redis_errors = 0
        self.fallback_events = 0
        self.invalidations = 0

    def _on_redis_failure(self, err: Exception) -> None:
        self.redis_errors += 1
        self._consecutive_redis_failures += 1
        self._last_failure_time = time.time()
        if (
            self._consecutive_redis_failures >= self.failure_threshold
            and self.state != CacheState.DEGRADED
        ):
            logger.warning(
                f"Redis failure threshold ({self.failure_threshold}) reached: {err}. "
                "Degrading cache mode to L1 local memory fallback."
            )
            self.state = CacheState.DEGRADED
            self.fallback_events += 1

    def _on_redis_success(self) -> None:
        if self.state == CacheState.DEGRADED or self._consecutive_redis_failures > 0:
            logger.info(
                "Redis connectivity verified. Restoring normal cache tier operation."
            )
            self.state = CacheState.NORMAL
            self._consecutive_redis_failures = 0

    def _evict_l1_lru_if_needed(self) -> None:
        while len(self._l1_cache) >= self.max_l1_items:
            oldest_key, entry = self._l1_cache.popitem(last=False)
            for tag in entry.tags:
                if tag in self._tag_to_keys:
                    self._tag_to_keys[tag].discard(oldest_key)
                    if not self._tag_to_keys[tag]:
                        del self._tag_to_keys[tag]

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: float | None = None,
        tags: set[str] | list[str] | None = None,
    ) -> None:
        """Store item in L1 and L2 (Redis) with tag indexing."""
        tag_set = set(tags or [])
        entry = CacheEntry(key=key, value=value, ttl_seconds=ttl_seconds, tags=tag_set)

        with self._lock:
            # L1 store
            if key in self._l1_cache:
                del self._l1_cache[key]
            else:
                self._evict_l1_lru_if_needed()

            self._l1_cache[key] = entry
            for tag in tag_set:
                if tag not in self._tag_to_keys:
                    self._tag_to_keys[tag] = set()
                self._tag_to_keys[tag].add(key)

        # L2 store if Redis is available and not degraded
        if self.redis_client and self.state != CacheState.DEGRADED:
            try:
                serialized = json.dumps({"value": value, "tags": list(tag_set)})
                if ttl_seconds:
                    self.redis_client.setex(key, int(ttl_seconds), serialized)
                else:
                    self.redis_client.set(key, serialized)
                self._on_redis_success()
            except Exception as e:
                self._on_redis_failure(e)

    def get(self, key: str) -> Any | None:
        """Retrieve item with L1 -> L2 lookup and transparent failure recovery."""
        with self._lock:
            # Check L1
            if key in self._l1_cache:
                entry = self._l1_cache[key]
                if entry.is_expired():
                    del self._l1_cache[key]
                    for tag in entry.tags:
                        if tag in self._tag_to_keys:
                            self._tag_to_keys[tag].discard(key)
                else:
                    self._l1_cache.move_to_end(key)
                    self.hits += 1
                    self.l1_hits += 1
                    return entry.value

        # Check L2 (Redis) if available
        if self.redis_client:
            # Check if probe retry is due when degraded
            if (
                self.state == CacheState.DEGRADED
                and time.time() - self._last_failure_time > self.recovery_probe_interval
            ):
                self.state = CacheState.RECOVERING

            try:
                raw = self.redis_client.get(key)
                if raw is not None:
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8")
                    data = json.loads(raw)
                    val = data["value"]
                    tags = set(data.get("tags", []))
                    # Promote to L1
                    with self._lock:
                        self._evict_l1_lru_if_needed()
                        self._l1_cache[key] = CacheEntry(key=key, value=val, tags=tags)
                        for tag in tags:
                            if tag not in self._tag_to_keys:
                                self._tag_to_keys[tag] = set()
                            self._tag_to_keys[tag].add(key)
                    self.hits += 1
                    self.l2_hits += 1
                    self._on_redis_success()
                    return val
            except Exception as e:
                self._on_redis_failure(e)

        self.misses += 1
        return None

    def invalidate(self, key: str) -> None:
        """Invalidate a single key across all tiers."""
        with self._lock:
            if key in self._l1_cache:
                entry = self._l1_cache.pop(key)
                for tag in entry.tags:
                    if tag in self._tag_to_keys:
                        self._tag_to_keys[tag].discard(key)
            self.invalidations += 1

        if self.redis_client:
            try:
                self.redis_client.delete(key)
            except Exception as e:
                self._on_redis_failure(e)

    def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all keys associated with a specific tag."""
        evicted_count = 0
        keys_to_evict: set[str] = set()

        with self._lock:
            if tag in self._tag_to_keys:
                keys_to_evict = set(self._tag_to_keys[tag])
                for k in keys_to_evict:
                    if k in self._l1_cache:
                        del self._l1_cache[k]
                        evicted_count += 1
                del self._tag_to_keys[tag]

        if keys_to_evict and self.redis_client:
            for k in keys_to_evict:
                try:
                    self.redis_client.delete(k)
                except Exception as e:
                    self._on_redis_failure(e)

        self.invalidations += evicted_count
        return evicted_count

    def invalidate_prefix(self, prefix: str) -> int:
        """Invalidate all keys starting with prefix."""
        evicted_count = 0
        keys_to_remove: list[str] = []

        with self._lock:
            for k in list(self._l1_cache.keys()):
                if k.startswith(prefix):
                    entry = self._l1_cache.pop(k)
                    keys_to_remove.append(k)
                    for tag in entry.tags:
                        if tag in self._tag_to_keys:
                            self._tag_to_keys[tag].discard(k)
                    evicted_count += 1

        if self.redis_client:
            try:
                for k in keys_to_remove:
                    self.redis_client.delete(k)
            except Exception as e:
                self._on_redis_failure(e)

        self.invalidations += evicted_count
        return evicted_count

    def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], Any],
        ttl_seconds: float | None = None,
        tags: set[str] | list[str] | None = None,
    ) -> Any:
        """Retrieve cached value or compute and store it atomically."""
        cached = self.get(key)
        if cached is not None:
            return cached
        val = compute_fn()
        self.set(key, val, ttl_seconds=ttl_seconds, tags=tags)
        return val

    # Async wrappers
    async def aget(self, key: str) -> Any | None:
        return await asyncio.to_thread(self.get, key)

    async def aset(
        self,
        key: str,
        value: Any,
        ttl_seconds: float | None = None,
        tags: set[str] | list[str] | None = None,
    ) -> None:
        await asyncio.to_thread(self.set, key, value, ttl_seconds, tags)

    async def ainvalidate(self, key: str) -> None:
        await asyncio.to_thread(self.invalidate, key)

    async def ainvalidate_by_tag(self, tag: str) -> int:
        return await asyncio.to_thread(self.invalidate_by_tag, tag)

    def clear(self) -> None:
        with self._lock:
            self._l1_cache.clear()
            self._tag_to_keys.clear()
