# ruff: noqa: PLR2004
"""Unit tests for Resilient Multi-tier Cache and Redis failure fallback."""

import time
from unittest.mock import MagicMock

import pytest

from amberclaw.cache.resilience import (
    CacheEntry,
    CacheState,
    ResilientCacheManager,
)


def test_cache_entry_ttl_expiration():
    entry = CacheEntry(key="k1", value="v1", ttl_seconds=0.05)
    assert not entry.is_expired()
    time.sleep(0.06)
    assert entry.is_expired()


def test_l1_lru_and_tag_invalidation():
    cache = ResilientCacheManager(max_l1_items=5)
    cache.set("a", "val_a", tags=["user_1"])
    cache.set("b", "val_b", tags=["user_1", "team_x"])

    assert cache.get("a") == "val_a"
    assert cache.get("b") == "val_b"

    # Invalidate by tag
    evicted = cache.invalidate_by_tag("team_x")
    assert evicted == 1
    assert cache.get("b") is None
    assert cache.get("a") == "val_a"

    # Prefix invalidation
    cache.set("pref_1", 100)
    cache.set("pref_2", 200)
    cache.set("other", 300)
    count = cache.invalidate_prefix("pref_")
    assert count == 2
    assert cache.get("pref_1") is None
    assert cache.get("pref_2") is None
    assert cache.get("other") == 300


def test_redis_failure_and_graceful_l1_degradation():
    mock_redis = MagicMock()
    mock_redis.set.side_effect = ConnectionError("Connection refused to Redis:6379")
    mock_redis.get.side_effect = ConnectionError("Connection refused to Redis:6379")

    cache = ResilientCacheManager(
        redis_client=mock_redis,
        failure_threshold=3,
        recovery_probe_interval_seconds=0.1,
    )
    assert cache.state == CacheState.NORMAL

    # First 2 operations fail in Redis, but still cached in L1
    cache.set("key_1", "safe_val")
    cache.set("key_2", "safe_val_2")
    assert cache.state == CacheState.NORMAL
    assert cache._consecutive_redis_failures == 2

    # 3rd failure trips the circuit breaker to DEGRADED
    cache.set("key_3", "safe_val_3")
    assert cache.state == CacheState.DEGRADED
    assert cache.fallback_events == 1

    # Operations still succeed using local L1 memory fallback
    assert cache.get("key_1") == "safe_val"
    assert cache.get("key_3") == "safe_val_3"

    # Recover Redis
    mock_redis.set.side_effect = None
    mock_redis.get.side_effect = None
    mock_redis.get.return_value = '{"value": "recovered_data", "tags": []}'

    # Wait for probe interval
    time.sleep(0.12)
    val = cache.get("recovered_key")
    assert val == "recovered_data"
    assert cache.state == CacheState.NORMAL


def test_get_or_compute():
    cache = ResilientCacheManager()
    call_count = 0

    def compute():
        nonlocal call_count
        call_count += 1
        return "expensive_result"

    res1 = cache.get_or_compute("calc_key", compute)
    res2 = cache.get_or_compute("calc_key", compute)

    assert res1 == "expensive_result"
    assert res2 == "expensive_result"
    assert call_count == 1
    assert cache.hits == 1


@pytest.mark.asyncio
async def test_async_cache_operations():
    cache = ResilientCacheManager()
    await cache.aset("async_k", "async_v", tags=["tag_a"])
    got = await cache.aget("async_k")
    assert got == "async_v"

    evicted = await cache.ainvalidate_by_tag("tag_a")
    assert evicted == 1
    assert await cache.aget("async_k") is None
