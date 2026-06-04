"""Unit tests for the Honcho Dialectic User Modeling Provider."""

import pytest

from amberclaw.memory.honcho_provider import HonchoProvider


@pytest.mark.asyncio
async def test_honcho_provider_mock_mode():
    # Initialize in Mock/Local mode without API key
    provider = HonchoProvider(api_key=None)

    # Verify peers/sessions fallback gracefully to dicts in mock mode
    peer = await provider.get_or_create_peer("user_1")
    assert isinstance(peer, dict)
    assert peer["mock"] is True

    session = await provider.get_or_create_session(
        session_id="session_1",
        user_id="user_1",
        agent_id="agent_1",
        observation_mode="directional",
    )
    assert isinstance(session, dict)
    assert session["mock"] is True


@pytest.mark.asyncio
async def test_honcho_provider_reasoning_passes():
    provider = HonchoProvider(api_key=None)

    # Test the three reasoning passes
    passes = await provider.run_reasoning_passes(
        user_id="user_123",
        agent_id="agent_456",
        message="I love chocolate ice cream.",
        role="user",
    )

    assert "initial_assessment" in passes
    assert "self_audit" in passes
    assert "reconciliation" in passes

    assert "Initial Assessment" in passes["initial_assessment"]
    assert "Self-Audit" in passes["self_audit"]
    assert "Reconciliation" in passes["reconciliation"]


@pytest.mark.asyncio
async def test_honcho_provider_process_turn_mock():
    provider = HonchoProvider(api_key=None)

    result = await provider.process_turn(
        session_id="session_abc",
        user_id="user_xyz",
        agent_id="agent_123",
        message="Hello AI",
        role="user",
        observation_mode="unified",
    )

    assert result["session_id"] == "session_abc"
    assert result["observation_mode"] == "unified"
    assert result["status"] == "mock"
    assert "reconciliation" in result["reasoning"]
