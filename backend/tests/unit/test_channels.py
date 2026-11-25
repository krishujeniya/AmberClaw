# ruff: noqa: PLR2004
"""Comprehensive unit tests for Section 10 Messaging Channels Upgrades:
- Channel capability matrix & feature queries
- Graceful degradation and fallback formatting for unsupported actions
- Channel token-bucket rate limiter with HTTP 429 adaptive backoff
- Exponential backoff reconnect manager with jitter
- Delivery latency, error rates, and throughput metrics tracking
- Cross-channel user identity mapping and conversation continuity
"""

import asyncio

import pytest

from amberclaw.channels import (
    ChannelCapability,
    ChannelMetricsTracker,
    ChannelRateLimiter,
    ChannelReconnectManager,
    ConnectionState,
    CrossChannelContinuityManager,
    check_channel_support,
    explain_unsupported_action,
    format_graceful_fallback,
    get_channel_capability,
    register_channel_capability,
)


@pytest.fixture(autouse=True)
def reset_channel_singletons():
    CrossChannelContinuityManager.get_instance().clear()
    yield
    CrossChannelContinuityManager.get_instance().clear()


# ==============================================================================
# 1. Channel Capability Matrix & Fallbacks
# ==============================================================================


def test_channel_capabilities_catalog_defaults():
    tg = get_channel_capability("telegram")
    assert tg.channel == "telegram"
    assert tg.voice_notes is True
    assert tg.threading is True
    assert tg.reactions is True
    assert tg.max_message_length == 4096

    discord = get_channel_capability("discord")
    assert discord.channel == "discord"
    assert discord.html is False
    assert discord.max_message_length == 2000

    email = get_channel_capability("email")
    assert email.reactions is False
    assert email.typing_indicator is False
    assert email.max_message_length >= 100000


def test_channel_feature_support_queries():
    assert check_channel_support("telegram", "voice_notes") is True
    assert check_channel_support("email", "reactions") is False
    assert check_channel_support("slack", "threading") is True
    assert check_channel_support("whatsapp", "threading") is False


def test_custom_channel_capability_registration():
    custom_cap = ChannelCapability(
        channel="my_custom_channel",
        markdown=True,
        images=True,
        max_message_length=1234,
        rate_limit_messages_per_sec=42.0,
    )
    register_channel_capability(custom_cap)

    retrieved = get_channel_capability("my_custom_channel")
    assert retrieved.max_message_length == 1234
    assert retrieved.rate_limit_messages_per_sec == 42.0


def test_explain_unsupported_actions():
    exp_reactions = explain_unsupported_action("email", "reactions")
    assert "reactions" in exp_reactions.lower()

    exp_voice = explain_unsupported_action("discord", "voice_notes")
    assert "voice notes" in exp_voice.lower()


def test_format_graceful_fallbacks():
    fb_reaction = format_graceful_fallback("email", "reactions", "👍")
    assert fb_reaction == "[Reaction: 👍]"

    fb_voice = format_graceful_fallback("discord", "voice_notes", "Hello from audio")
    assert "Voice Note Transcript" in fb_voice
    assert "Hello from audio" in fb_voice

    fb_thread = format_graceful_fallback(
        "whatsapp", "threading", "Replying to previous message"
    )
    assert "[Thread Reply]" in fb_thread


# ==============================================================================
# 2. Rate Limiting & Resilience
# ==============================================================================


@pytest.mark.asyncio
async def test_channel_rate_limiter_acquire_success():
    limiter = ChannelRateLimiter()

    # Fast acquisitions within capacity
    ok1 = await limiter.acquire("telegram", cost=1.0)
    ok2 = await limiter.acquire("telegram", cost=1.0)
    assert ok1 is True
    assert ok2 is True


@pytest.mark.asyncio
async def test_channel_rate_limiter_handles_429_backoff():
    limiter = ChannelRateLimiter()

    limiter.report_rate_limit("telegram", retry_after_sec=0.2)
    assert limiter.is_blocked("telegram") is True

    # Immediate acquire should fail or wait
    acquired = await limiter.acquire("telegram", cost=1.0, timeout=0.05)
    assert acquired is False

    # After waiting out the cooldown, acquire succeeds
    await asyncio.sleep(0.22)
    assert limiter.is_blocked("telegram") is False
    acquired_after = await limiter.acquire("telegram", cost=1.0, timeout=1.0)
    assert acquired_after is True


def test_reconnect_manager_exponential_backoff_and_reset():
    mgr = ChannelReconnectManager(
        initial_delay=1.0, multiplier=2.0, max_delay=10.0, jitter_ratio=0.0
    )

    delay1 = mgr.record_failure("discord")
    assert 0.9 <= delay1 <= 1.1
    assert mgr.get_state("discord") == ConnectionState.BACKOFF

    delay2 = mgr.record_failure("discord")
    assert 1.9 <= delay2 <= 2.1

    delay3 = mgr.record_failure("discord")
    assert 3.9 <= delay3 <= 4.1

    # Reset on success
    mgr.record_success("discord")
    assert mgr.get_state("discord") == ConnectionState.CONNECTED

    # Subsequent failure starts from initial delay again
    delay_fresh = mgr.record_failure("discord")
    assert 0.9 <= delay_fresh <= 1.1


def test_reconnect_manager_max_retries_threshold():
    mgr = ChannelReconnectManager(initial_delay=0.1)

    for _ in range(4):
        assert mgr.should_retry("slack", max_retries=5) is True
        mgr.record_failure("slack")

    mgr.record_failure("slack")  # 5th failure
    assert mgr.should_retry("slack", max_retries=5) is False
    assert mgr.get_state("slack") == ConnectionState.FAILED


def test_channel_metrics_tracker_computations():
    tracker = ChannelMetricsTracker()

    tracker.record_inbound("telegram")
    tracker.record_inbound("telegram")
    tracker.record_reconnect("telegram")

    tracker.record_delivery("telegram", duration_ms=50.0, success=True)
    tracker.record_delivery("telegram", duration_ms=100.0, success=True)
    tracker.record_delivery("telegram", duration_ms=200.0, success=False)

    stats = tracker.get_stats("telegram")
    assert stats["messages_received"] == 2
    assert stats["messages_sent"] == 2
    assert stats["messages_failed"] == 1
    assert stats["reconnect_events"] == 1
    assert 0.60 <= stats["success_rate"] <= 0.70
    assert stats["latency_p50_ms"] > 0


# ==============================================================================
# 3. Cross-Channel Conversation Continuity
# ==============================================================================


def test_cross_channel_identity_linking_and_resolution():
    continuity = CrossChannelContinuityManager.get_instance()

    continuity.link_identity(
        canonical_user_id="user_alice",
        channel="telegram",
        channel_user_id="tg_12345",
    )
    continuity.link_identity(
        canonical_user_id="user_alice",
        channel="discord",
        channel_user_id="disc_98765",
    )

    # Resolution
    assert continuity.resolve_canonical_user("telegram", "tg_12345") == "user_alice"
    assert continuity.resolve_canonical_user("discord", "disc_98765") == "user_alice"
    # Unlinked user falls back to channel user ID
    assert (
        continuity.resolve_canonical_user("slack", "random_user") == "slack_random_user"
    )

    linked = continuity.get_linked_identities("user_alice")
    assert len(linked) == 2
    assert ("telegram", "tg_12345") in linked
    assert ("discord", "disc_98765") in linked


def test_cross_channel_session_continuity_and_handover():
    continuity = CrossChannelContinuityManager.get_instance()

    continuity.link_identity("user_bob", "telegram", "bob_tg")
    continuity.link_identity("user_bob", "web", "bob_web")

    # Bind session to canonical user
    continuity.bind_session("user_bob", "session_abc_123")

    # Both channels resolve the same conversation session
    assert continuity.get_active_session("telegram", "bob_tg") == "session_abc_123"
    assert continuity.get_active_session("web", "bob_web") == "session_abc_123"

    # Explicit session handover between channels
    continuity.handover_session(
        from_channel="telegram",
        from_user_id="bob_tg",
        to_channel="slack",
        to_user_id="bob_slack",
        session_id="session_handed_over_999",
    )
    assert (
        continuity.get_active_session("slack", "bob_slack") == "session_handed_over_999"
    )


def test_unlink_identity():
    continuity = CrossChannelContinuityManager.get_instance()
    continuity.link_identity("user_charlie", "feishu", "fs_111")

    assert continuity.resolve_canonical_user("feishu", "fs_111") == "user_charlie"
    assert continuity.unlink_identity("feishu", "fs_111") is True
    assert continuity.resolve_canonical_user("feishu", "fs_111") == "feishu_fs_111"
