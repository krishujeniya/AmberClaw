import pytest

def get_system_prompt() -> str:
    return "You are AmberClaw, an AI assistant."

def test_prompt_regression():
    prompt = get_system_prompt()
    # Simple snapshot representation without external plugins
    expected_prompt = "You are AmberClaw, an AI assistant."
    assert prompt == expected_prompt
