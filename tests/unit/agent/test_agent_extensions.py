"""Unit tests for agent learning, compression, personality, and insights modules."""

from pathlib import Path

from amberclaw.agent.compression import ContextCompressor
from amberclaw.agent.insights import InsightsEngine
from amberclaw.agent.learning.feedback import FeedbackCollector, UserFeedback
from amberclaw.agent.learning.memory_nudges import (
    MemoryNudgeEvaluator,
    NudgeTriggerType,
)
from amberclaw.agent.personality import PersonalityProfile


def test_feedback_collector():
    collector = FeedbackCollector()

    # Empty stats
    assert collector.get_summary_stats()["total"] == 0

    # Record feedback
    collector.record_feedback(
        UserFeedback(session_id="s1", turn_index=1, rating="positive")
    )
    collector.record_feedback(
        UserFeedback(
            session_id="s1",
            turn_index=2,
            rating="negative",
            critique="Too verbose",
            correction="Make response under 3 sentences.",
        )
    )

    stats = collector.get_summary_stats()
    expected_total = 2
    expected_rate = 0.5
    assert stats["total"] == expected_total
    assert stats["positive"] == 1
    assert stats["negative"] == 1
    assert stats["satisfaction_rate"] == expected_rate

    corrections = collector.get_corrections()
    assert len(corrections) == 1
    assert "under 3 sentences" in corrections[0]["correction"]


def test_memory_nudge_evaluator(tmp_path: Path):
    evaluator = MemoryNudgeEvaluator(workspace=tmp_path)

    # 1. No nudge needed
    event = evaluator.evaluate([{"role": "user", "content": "hello"}], "hello")
    assert event is None

    # 2. Keyword pattern nudge
    event_pref = evaluator.evaluate(
        [{"role": "user", "content": "I prefer using PostgreSQL for databases."}],
        "I prefer using PostgreSQL for databases.",
    )
    assert event_pref is not None
    assert event_pref.trigger_type == NudgeTriggerType.KEYWORD_PATTERN
    assert "long-term memory" in event_pref.message


def test_context_compressor():
    compressor = ContextCompressor(max_tokens=50, keep_recent=2)

    messages = [
        {"role": "system", "content": "You are AmberClaw."},
        {"role": "user", "content": "Let us talk about large scale distributed architectures and database replication strategies in cloud environments."},
        {"role": "assistant", "content": "Distributed databases use consensus protocols such as Raft or Paxos along with multi-region replication."},
        {"role": "user", "content": "What about failover mechanisms?"},
        {"role": "assistant", "content": "Failover relies on automatic heartbeat quorum sensing and leader reelection."},
        {"role": "user", "content": "Give me a summary."},
    ]

    result = compressor.compress(messages)
    assert result.summarized_turn_count > 0
    assert result.tokens_after < result.tokens_before
    assert len(result.compressed_messages) <= len(messages)
    assert any("[Context Summary of Previous Turns]" in str(m.get("content")) for m in result.compressed_messages)


def test_personality_profile():
    profile = PersonalityProfile(
        name="ClawExpert",
        tone="technical",
        verbosity="detailed",
        technical_depth=4,
        custom_directives=["Use type annotations everywhere."],
    )

    directive = profile.render_system_prompt_directive()
    assert "You are ClawExpert." in directive
    assert "Technical Depth: Level 4 of 5." in directive
    assert "Use type annotations everywhere." in directive


def test_insights_engine():
    engine = InsightsEngine()

    messages = [
        {"role": "user", "content": "Please write a python script with pytest tests and verify using docker compose."},
        {"role": "assistant", "content": "Here is the code."},
    ]

    insights = engine.extract_insights(messages)
    types = [i.insight_type for i in insights]
    assert "preference" in types
    assert "workflow" in types
    assert any("python" in i.description.lower() for i in insights)
