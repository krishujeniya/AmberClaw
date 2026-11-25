"""Offline bootstrap probes, truthful readiness, and fallback ownership."""

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest

from amberclaw import bootstrap
from amberclaw.bootstrap import SafeModeBootstrapper, bootstrap_system
from amberclaw.database import postgres, redis_client


def set_health(
    monkeypatch: pytest.MonkeyPatch,
    bootstrapper: SafeModeBootstrapper,
    *,
    database: bool = True,
    cache: bool = True,
    vector: bool = True,
) -> None:
    monkeypatch.setattr(
        bootstrapper, "verify_database", AsyncMock(return_value=database)
    )
    monkeypatch.setattr(bootstrapper, "verify_cache", AsyncMock(return_value=cache))
    monkeypatch.setattr(
        bootstrapper, "verify_vector_store", AsyncMock(return_value=vector)
    )


@pytest.mark.asyncio
async def test_baseline_regression_vector_without_probe_is_unavailable() -> None:
    assert await SafeModeBootstrapper().verify_vector_store() is False


@pytest.mark.asyncio
async def test_baseline_regression_repeated_bootstrap_resets_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrapper = SafeModeBootstrapper()
    set_health(monkeypatch, bootstrapper, database=False)
    first = await bootstrapper.bootstrap()
    assert first.degraded_components == ["storage_database"]
    set_health(monkeypatch, bootstrapper)
    second = await bootstrapper.bootstrap()
    assert second is not first
    assert second.degraded_components == []
    assert second.active_fallbacks == {}
    assert second.safe_mode is False
    assert second.system_ready is True


@pytest.mark.asyncio
async def test_baseline_regression_disabled_safe_mode_has_no_activated_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrapper = SafeModeBootstrapper(allow_safe_mode=False)
    set_health(monkeypatch, bootstrapper, database=False, cache=False, vector=False)
    with pytest.raises(RuntimeError, match="safe-mode fallback is disabled"):
        await bootstrapper.bootstrap()
    assert bootstrapper.status.system_ready is False
    assert bootstrapper.status.active_fallbacks == {}


@pytest.mark.asyncio
async def test_baseline_regression_no_fictional_database_or_vector_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrapper = SafeModeBootstrapper()
    set_health(monkeypatch, bootstrapper, database=False, cache=False, vector=False)
    status = await bootstrapper.bootstrap()
    assert status.active_fallbacks == {"cache": "local_lru_memory"}
    assert status.system_ready is False
    assert status.cache_fallback is not None
    status.cache_fallback.set("key", "value")
    assert status.cache_fallback.get("key") == "value"
    status.close()


@pytest.mark.asyncio
async def test_configured_database_probe_executes_select_and_closes_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = MagicMock()
    result = MagicMock()
    result.scalar_one.return_value = 1
    session.execute = AsyncMock(return_value=result)
    closed = []

    async def sessions() -> AsyncGenerator[MagicMock, None]:
        try:
            yield session
        finally:
            closed.append(True)

    monkeypatch.setattr(postgres, "get_db_session", sessions)
    assert await SafeModeBootstrapper().verify_database() is True
    assert str(session.execute.call_args.args[0]) == "SELECT 1"
    assert closed == [True]


@pytest.mark.asyncio
async def test_configured_database_failure_is_unavailable_and_closes_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = MagicMock()
    session.execute = AsyncMock(side_effect=ConnectionError("offline"))
    closed = []

    async def sessions() -> AsyncGenerator[MagicMock, None]:
        try:
            yield session
        finally:
            closed.append(True)

    monkeypatch.setattr(postgres, "get_db_session", sessions)
    assert await SafeModeBootstrapper().verify_database() is False
    assert closed == [True]


@pytest.mark.asyncio
async def test_redis_probe_pings_configured_client_and_handles_absence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MagicMock()
    client.ping = AsyncMock(return_value=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: client)
    assert await SafeModeBootstrapper().verify_cache() is True
    client.ping.assert_awaited_once_with()
    client.aclose.assert_not_called()
    monkeypatch.setattr(redis_client, "get_redis", lambda: None)
    assert await SafeModeBootstrapper().verify_cache() is False


@pytest.mark.asyncio
async def test_injected_health_probes_and_cache_resource_lifecycle() -> None:
    database = AsyncMock(return_value=True)
    cache = AsyncMock(return_value=False)
    vector = AsyncMock(return_value=True)
    bootstrapper = SafeModeBootstrapper(
        database_probe=database, cache_probe=cache, vector_probe=vector
    )
    status = await bootstrapper.bootstrap()
    assert status.system_ready is True
    assert status.safe_mode is True
    assert status.active_fallbacks == {"cache": "local_lru_memory"}
    local_cache = status.cache_fallback
    assert local_cache is not None
    local_cache.set("key", "value")
    database.assert_awaited_once_with()
    cache.assert_awaited_once_with()
    vector.assert_awaited_once_with()
    cache.return_value = True
    healthy = await bootstrapper.bootstrap()
    assert healthy.system_ready is True
    assert healthy.safe_mode is False
    assert healthy.cache_fallback is None
    assert status.cache_fallback is None
    assert status.active_fallbacks == {}
    assert status.system_ready is False
    assert local_cache.get("key") is None
    bootstrapper.close()


@pytest.mark.asyncio
async def test_failed_local_fallback_does_not_claim_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrapper = SafeModeBootstrapper()
    set_health(monkeypatch, bootstrapper, cache=False)
    monkeypatch.setattr(
        bootstrap,
        "ResilientCacheManager",
        MagicMock(side_effect=RuntimeError("allocation failed")),
    )
    status = await bootstrapper.bootstrap()
    assert status.safe_mode is True
    assert status.system_ready is False
    assert status.active_fallbacks == {}
    assert status.cache_fallback is None


@pytest.mark.asyncio
async def test_unhealthy_local_fallback_is_cleared_and_not_advertised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrapper = SafeModeBootstrapper()
    set_health(monkeypatch, bootstrapper, cache=False)
    local_cache = MagicMock()
    local_cache.get.return_value = None
    monkeypatch.setattr(
        bootstrap, "ResilientCacheManager", MagicMock(return_value=local_cache)
    )
    status = await bootstrapper.bootstrap()
    assert status.system_ready is False
    assert status.active_fallbacks == {}
    assert status.cache_fallback is None
    local_cache.clear.assert_called_once_with()


@pytest.mark.asyncio
async def test_probe_exceptions_and_timeouts_fail_closed() -> None:
    bootstrapper = SafeModeBootstrapper(
        database_probe=AsyncMock(side_effect=ConnectionError("offline")),
        cache_probe=AsyncMock(side_effect=TimeoutError("offline")),
        vector_probe=AsyncMock(return_value=False),
    )
    status = await bootstrapper.bootstrap()
    assert status.degraded_components == [
        "storage_database",
        "distributed_cache",
        "vector_store",
    ]
    assert status.system_ready is False
    status.close()


@pytest.mark.asyncio
async def test_hung_probe_is_cancelled_at_its_deadline() -> None:
    finished = []

    async def hanging_probe() -> bool:
        try:
            await asyncio.Event().wait()
            return True
        finally:
            finished.append(True)

    bootstrapper = SafeModeBootstrapper(vector_probe=hanging_probe)
    bootstrapper._PROBE_TIMEOUT_SECONDS = 0.01
    assert await bootstrapper.verify_vector_store() is False
    assert finished == [True]


@pytest.mark.asyncio
async def test_bootstrap_helper_returns_accessible_fallback_and_excludes_runtime_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        SafeModeBootstrapper, "verify_database", AsyncMock(return_value=True)
    )
    monkeypatch.setattr(
        SafeModeBootstrapper, "verify_cache", AsyncMock(return_value=False)
    )
    monkeypatch.setattr(
        SafeModeBootstrapper, "verify_vector_store", AsyncMock(return_value=True)
    )
    status = await bootstrap_system()
    assert status.cache_fallback is not None
    assert status.system_ready is True
    assert "cache_fallback" not in status.model_dump()
    assert '"local_lru_memory"' in status.model_dump_json()
    status.close()
    assert status.cache_fallback is None
    assert status.system_ready is False
