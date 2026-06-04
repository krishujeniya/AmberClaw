"""Unit tests for model capability detection and dynamic routing in LiteLLMProvider."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from amberclaw.providers.litellm_provider import LiteLLMProvider
from amberclaw.providers.base import LLMResponse


@pytest.fixture
def mock_litellm():
    with patch("amberclaw.providers.litellm_provider.litellm") as mock:
        yield mock


@pytest.mark.asyncio
async def test_get_capabilities_via_litellm(mock_litellm):
    # Mock litellm.get_model_info for a specific model
    mock_litellm.get_model_info.return_value = {
        "supports_vision": True,
        "supports_function_calling": True,
        "supports_response_schema": True,
        "max_input_tokens": 128000,
        "supports_prompt_caching": True,
    }

    provider = LiteLLMProvider(api_key="test-key", default_model="custom-model")
    caps = provider.get_capabilities("custom-model")

    assert caps["vision"] is True
    assert caps["tools"] is True
    assert caps["json"] is True
    assert caps["context_size"] == 128000
    assert caps["prompt_caching"] is True


def test_get_capabilities_fallback_logic(mock_litellm):
    # Mock get_model_info to raise an exception, testing fallbacks
    mock_litellm.get_model_info.side_effect = Exception("offline")

    provider = LiteLLMProvider(api_key="test-key", default_model="unknown-model")
    
    # Check vision and context window resolution for claude
    caps_claude = provider.get_capabilities("anthropic/claude-3-5-sonnet")
    assert caps_claude["vision"] is True
    assert caps_claude["context_size"] == 200000
    assert caps_claude["prompt_caching"] is True

    # Check reasoning model detection
    caps_r1 = provider.get_capabilities("deepseek/deepseek-r1")
    assert caps_r1["reasoning"] is True


def test_analyze_requirements(mock_litellm):
    provider = LiteLLMProvider(api_key="test-key")

    # 1. Vision prompt
    messages_vision = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image:"},
                {"type": "image_url", "image_url": "data:image/png;base64,abc"}
            ]
        }
    ]
    reqs_vision = provider._analyze_requirements(messages_vision)
    assert reqs_vision["vision"] is True

    # 2. Reasoning prompt via keywords
    messages_reasoning = [
        {"role": "user", "content": "Please reason deeply and explain step-by-step why 1+1=2."}
    ]
    reqs_reasoning = provider._analyze_requirements(messages_reasoning)
    assert reqs_reasoning["reasoning"] is True


@pytest.mark.asyncio
async def test_dynamic_routing_to_fallback(mock_litellm):
    # Setup LiteLLMProvider with a primary model that lacks vision, and a fallback that supports it
    provider = LiteLLMProvider(
        api_key="test-key",
        default_model="openai/gpt-3.5-turbo",
        fallback_models=["anthropic/claude-3-5-sonnet", "deepseek/deepseek-r1"]
    )

    # Mock capabilities for models
    def mock_get_capabilities(model):
        if "gpt-3.5" in model:
            return {"vision": False, "reasoning": False, "context_size": 4096}
        elif "claude-3-5" in model:
            return {"vision": True, "reasoning": False, "context_size": 200000}
        elif "deepseek-r1" in model:
            return {"vision": False, "reasoning": True, "context_size": 64000}
        return {"vision": False, "reasoning": False, "context_size": 4096}

    provider.get_capabilities = MagicMock(side_effect=mock_get_capabilities)

    # Mock acompletion call
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="Vision result", tool_calls=[]), finish_reason="stop")
    ]

    with patch("amberclaw.providers.litellm_provider.acompletion", new_callable=AsyncMock) as mock_acompletion:
        mock_acompletion.return_value = mock_response

        # Trigger chat with a vision message
        messages = [
            {
                "role": "user",
                "content": [{"type": "image_url", "image_url": "http://example.com/img.png"}]
            }
        ]

        await provider.chat(messages=messages)

        # Verify acompletion was called with the vision-supporting fallback model
        # (resolved from optimal model 'anthropic/claude-3-5-sonnet')
        called_args, called_kwargs = mock_acompletion.call_args
        assert "claude-3-5-sonnet" in called_kwargs["model"]

