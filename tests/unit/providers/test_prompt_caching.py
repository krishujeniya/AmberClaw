"""Unit tests for prompt caching and dynamic breakpoints in LiteLLMProvider."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from amberclaw.providers.litellm_provider import LiteLLMProvider
from amberclaw.providers.registry import ProviderSpec


@pytest.fixture
def mock_litellm():
    with patch("amberclaw.providers.litellm_provider.litellm") as mock:
        yield mock


def test_supports_cache_control_flag():
    provider_enabled = LiteLLMProvider(
        api_key="test-key",
        default_model="anthropic/claude-3-5-sonnet",
        enable_prompt_caching=True
    )
    provider_disabled = LiteLLMProvider(
        api_key="test-key",
        default_model="anthropic/claude-3-5-sonnet",
        enable_prompt_caching=False
    )

    # Mock capabilities to support caching
    def mock_get_capabilities(model):
        return {"prompt_caching": True}

    provider_enabled.get_capabilities = MagicMock(side_effect=mock_get_capabilities)
    provider_disabled.get_capabilities = MagicMock(side_effect=mock_get_capabilities)

    assert provider_enabled._supports_cache_control("anthropic/claude-3-5-sonnet") is True
    assert provider_disabled._supports_cache_control("anthropic/claude-3-5-sonnet") is False


def test_apply_cache_control_breakpoints():
    provider = LiteLLMProvider(
        api_key="test-key",
        default_model="anthropic/claude-3-5-sonnet",
        enable_prompt_caching=True
    )

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello! (Turn 1)"},
        {"role": "assistant", "content": "Hi there! (Turn 2)"},
        {"role": "user", "content": "How's the weather? (Turn 3)"},
        {"role": "assistant", "content": "It's sunny. (Turn 4)"},
        {"role": "user", "content": "What should I do? (Turn 5)"},
    ]

    tools = [
        {"name": "get_weather", "description": "Get current weather"}
    ]

    new_msgs, new_tools = provider._apply_cache_control(messages, tools)

    # 1. System prompt gets cached
    assert isinstance(new_msgs[0]["content"], list)
    assert new_msgs[0]["content"][0]["cache_control"] == {"type": "ephemeral"}

    # 2. Last tool gets cached
    assert new_tools[0]["cache_control"] == {"type": "ephemeral"}

    # 3. Middle user/assistant turn (index 3: "How's the weather?")
    # msg_indices = [1, 2, 3, 4, 5] -> middle index is 3 (index of "How's the weather?")
    assert isinstance(new_msgs[3]["content"], list)
    assert new_msgs[3]["content"][0]["cache_control"] == {"type": "ephemeral"}

    # 4. Second-to-last user/assistant turn (index 4: "It's sunny.")
    assert isinstance(new_msgs[4]["content"], list)
    assert new_msgs[4]["content"][0]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.asyncio
async def test_openrouter_edge_cache_header(mock_litellm):
    # Setup LiteLLMProvider with openrouter gateway
    provider = LiteLLMProvider(
        api_key="sk-or-testkey",
        default_model="anthropic/claude-3-5-sonnet",
        provider_name="openrouter",
        enable_prompt_caching=True
    )

    # Mock acompletion
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="Hello", tool_calls=[]), finish_reason="stop")
    ]

    with patch("amberclaw.providers.litellm_provider.acompletion", new_callable=AsyncMock) as mock_acompletion:
        mock_acompletion.return_value = mock_response

        messages = [{"role": "user", "content": "Hello"}]
        await provider.chat(messages=messages)

        # Assert X-OpenRouter-Cache header is present
        called_args, called_kwargs = mock_acompletion.call_args
        assert called_kwargs["extra_headers"].get("X-OpenRouter-Cache") == "true"
