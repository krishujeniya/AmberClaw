# ruff: noqa: PLR2004
"""Unit tests for the amberclaw.inference package (credentials, health, PII, profiles, proxy, router)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from amberclaw.inference.credentials import InferenceCredentialManager
from amberclaw.inference.health import InferenceHealthMonitor, ProviderHealthStatus
from amberclaw.inference.pii_scanner import InferencePIIScanner
from amberclaw.inference.profiles import (
    InferenceProfile,
    InferenceTier,
    ProfileRegistry,
)
from amberclaw.inference.proxy import InferenceProxyConfig, InferenceProxyManager
from amberclaw.inference.router import InferenceRequest, InferenceRouter

# ==============================================================================
# Credentials Tests
# ==============================================================================


def test_credential_manager(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-1234567890abcdef")
    mgr = InferenceCredentialManager()

    assert mgr.has_credential("anthropic") is True
    cred = mgr.get_credential("anthropic")
    assert cred is not None
    assert cred.masked_key.startswith("sk-a...")

    # Set dynamic
    mgr.set_credential("openai", api_key="sk-proj-testkey987654321")
    assert mgr.has_credential("openai") is True
    assert "openai" in mgr.list_configured_providers()


# ==============================================================================
# Health Monitor Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_health_monitor_probes():
    monitor = InferenceHealthMonitor(latency_threshold_ms=50.0)

    # Success probe
    async def _healthy_probe() -> bool:
        await asyncio.sleep(0.01)
        return True

    res = await monitor.probe_provider("groq", probe_fn=_healthy_probe)
    assert res.status == ProviderHealthStatus.HEALTHY
    assert res.latency_ms > 0

    # Degraded probe (latency exceeds threshold)
    async def _slow_probe() -> bool:
        await asyncio.sleep(0.06)
        return True

    res_slow = await monitor.probe_provider("groq", probe_fn=_slow_probe)
    assert res_slow.status == ProviderHealthStatus.DEGRADED

    # Failing probe
    async def _failing_probe() -> bool:
        raise ConnectionResetError("Remote server refused connection")

    res_fail = await monitor.probe_provider("azure", probe_fn=_failing_probe)
    assert res_fail.status == ProviderHealthStatus.UNAVAILABLE
    assert "refused connection" in (res_fail.error or "")


# ==============================================================================
# PII Scanner Tests
# ==============================================================================


def test_pii_scanner():
    scanner = InferencePIIScanner()

    dirty_text = (
        "Contact me at alice.smith@enterprise.org or (555) 234-5678. "
        "SSN is 000-12-3456 and token is sk-1234567890123456789012."
    )
    result = scanner.scan(dirty_text)
    assert result.has_pii is True
    assert len(result.matches) >= 4

    sanitized = result.sanitized_text
    assert "alice.smith@enterprise.org" not in sanitized
    assert "000-12-3456" not in sanitized
    assert "[REDACTED_EMAIL]" in sanitized
    assert "[REDACTED_SSN]" in sanitized

    # Clean text
    clean_res = scanner.scan("This is completely benign documentation text.")
    assert clean_res.has_pii is False
    assert len(clean_res.matches) == 0


# ==============================================================================
# Profiles Tests
# ==============================================================================


def test_profile_registry():
    registry = ProfileRegistry()
    assert len(registry.list_profiles()) >= 5

    fast_profile = registry.get_profile("fast")
    assert fast_profile.tier == InferenceTier.FAST
    assert "mini" in fast_profile.model or "haiku" in fast_profile.model

    # Custom registration
    custom = InferenceProfile(
        name="edge-custom",
        tier=InferenceTier.FAST,
        model="local/edge-model-q4",
        temperature=0.3,
    )
    registry.register_profile(custom)
    retrieved = registry.get_profile("edge-custom")
    assert retrieved.name == "edge-custom"
    assert retrieved.model == "local/edge-model-q4"


# ==============================================================================
# Proxy & Circuit Breaker Tests
# ==============================================================================


def test_circuit_breaker():
    config = InferenceProxyConfig(
        circuit_breaker_failure_threshold=2,
        circuit_breaker_recovery_seconds=0.1,
    )
    proxy_mgr = InferenceProxyManager(config=config)

    assert proxy_mgr.is_available("deepseek") is True

    proxy_mgr.record_failure("deepseek")
    assert proxy_mgr.is_available("deepseek") is True

    proxy_mgr.record_failure("deepseek")
    # Threshold reached: circuit breaker tripped
    assert proxy_mgr.is_available("deepseek") is False

    proxy_mgr.record_success("deepseek")
    assert proxy_mgr.is_available("deepseek") is True


# ==============================================================================
# Inference Router Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_inference_router_dispatch_and_failover():
    mock_llm = MagicMock()
    # First model fails, fallback model succeeds
    mock_llm.generate = AsyncMock(
        side_effect=[
            RuntimeError("Primary model quota exceeded"),
            "Fallback completion response.",
        ]
    )

    router = InferenceRouter(llm_router=mock_llm)
    req = InferenceRequest(
        prompt="Tell me about user test@example.com",
        profile="fast",
        sanitize_pii=True,
    )

    resp = await router.execute(req)
    assert resp.reply == "Fallback completion response."
    assert resp.pii_sanitized is True
    assert resp.latency_ms > 0
    assert mock_llm.generate.await_count == 2
