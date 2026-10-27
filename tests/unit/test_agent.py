# ruff: noqa: PLR2004
"""Unit tests for AmberClaw Agent core, ContextBuilder, PersonalityProfile, and Compression."""

from pathlib import Path

from amberclaw.agent.compression import ContextCompressor
from amberclaw.agent.context import ContextBuilder
from amberclaw.agent.personality import PersonalityProfile
from amberclaw.agent.token_counter import count_tokens

# ==============================================================================
# 1. ContextBuilder & System Prompt Construction
# ==============================================================================


def test_context_builder_system_prompt(tmp_path: Path):
    builder = ContextBuilder(workspace=tmp_path)
    prompt = builder.build_system_prompt()

    assert "AmberClaw" in prompt or "Python" in prompt
    assert str(tmp_path) in prompt or "workspace" in prompt.lower()


def test_context_builder_loads_bootstrap_files(tmp_path: Path):
    user_file = tmp_path / "USER.md"
    user_file.write_text(
        "# User Preferences\nAlways use strict type hints.", encoding="utf-8"
    )

    soul_file = tmp_path / "SOUL.md"
    soul_file.write_text("# Agent Soul\nBe precise and direct.", encoding="utf-8")

    builder = ContextBuilder(workspace=tmp_path)
    prompt = builder.build_system_prompt()

    assert "Always use strict type hints" in prompt
    assert "Be precise and direct" in prompt


# ==============================================================================
# 2. PersonalityProfile & Conditioning
# ==============================================================================


def test_personality_profile_rendering():
    profile = PersonalityProfile(
        name="SecurityBot",
        tone="technical",
        verbosity="minimal",
        technical_depth=5,
        custom_directives=["Never output plaintext passwords."],
    )

    rendered = profile.render_system_prompt_directive()
    assert "You are SecurityBot." in rendered
    assert "Tone: Technical." in rendered
    assert "Verbosity: Minimal." in rendered
    assert "Level 5 of 5." in rendered
    assert "Never output plaintext passwords." in rendered


def test_personality_profile_concise_tone():
    profile = PersonalityProfile(tone="concise")
    rendered = profile.render_system_prompt_directive()
    assert "Prioritize brevity" in rendered


# ==============================================================================
# 3. ContextCompressor
# ==============================================================================


def test_context_compressor_noop_when_under_limit():
    compressor = ContextCompressor(max_tokens=1000, keep_recent=4)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "Hi there!"},
    ]

    res = compressor.compress(messages)
    assert len(res.compressed_messages) == 3
    assert res.summarized_turn_count == 0
    assert res.compression_ratio == 1.0


def test_context_compressor_condenses_older_turns():
    compressor = ContextCompressor(max_tokens=50, keep_recent=2)
    messages = [
        {"role": "system", "content": "System prompt."},
        {"role": "user", "content": "A" * 100},
        {"role": "assistant", "content": "B" * 100},
        {"role": "user", "content": "C" * 100},
        {"role": "assistant", "content": "D" * 100},
        {"role": "user", "content": "Recent question 1"},
        {"role": "assistant", "content": "Recent answer 2"},
    ]

    res = compressor.compress(messages)
    assert res.summarized_turn_count > 0
    assert res.tokens_after < res.tokens_before
    # Recent turns must be preserved intact
    assert res.compressed_messages[-1]["content"] == "Recent answer 2"
    assert res.compressed_messages[-2]["content"] == "Recent question 1"


# ==============================================================================
# 4. Token Counting
# ==============================================================================


def test_token_counter_basic():
    tokens_short = count_tokens([{"role": "user", "content": "Hello world"}])
    tokens_long = count_tokens([{"role": "user", "content": "Hello world " * 50}])
    assert tokens_short > 0
    assert tokens_long > tokens_short
