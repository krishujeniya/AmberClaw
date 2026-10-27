import pytest
from amberclaw.agent.loop import count_tokens


def test_count_tokens_accurate():
    messages = [
        {"role": "system", "content": "You are AmberClaw AI OS, an open zero-trust AI assistant."},
        {"role": "user", "content": "Run a system diagnosis on the agent runtime loop."},
    ]

    tokens = count_tokens(messages, model="gpt-4o")
    assert isinstance(tokens, int)
    assert tokens > 0
    # Expected ~30-40 tokens for this sample prompt
    assert 20 <= tokens <= 60


def test_count_tokens_empty_messages():
    tokens = count_tokens([], model="gpt-4o")
    assert tokens == 0
