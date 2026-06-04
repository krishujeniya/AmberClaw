"""Unit tests for JSON Mode and Strict Tool Calling enforcement in LiteLLMProvider."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from amberclaw.providers.litellm_provider import LiteLLMProvider
from amberclaw.providers.base import LLMResponse


@pytest.fixture
def mock_litellm():
    with patch("amberclaw.providers.litellm_provider.litellm") as mock:
        yield mock


def test_make_schema_strict():
    provider = LiteLLMProvider(api_key="test-key")

    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "address": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "zip": {"type": "string"},
                },
                "required": ["city"],
            },
        },
        "required": ["name"],
    }

    strict_schema = provider._make_schema_strict(schema)

    # 1. Root object properties
    assert strict_schema["additionalProperties"] is False
    assert sorted(strict_schema["required"]) == ["address", "age", "name"]

    # 2. Nested object properties
    nested = strict_schema["properties"]["address"]
    assert nested["additionalProperties"] is False
    assert sorted(nested["required"]) == ["city", "zip"]


def test_make_tool_strict():
    provider = LiteLLMProvider(api_key="test-key")

    tool = {
        "type": "function",
        "function": {
            "name": "get_user",
            "description": "Retrieve user details",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                },
            },
        },
    }

    strict_tool = provider._make_tool_strict(tool)

    assert strict_tool["function"]["strict"] is True
    assert strict_tool["function"]["parameters"]["additionalProperties"] is False
    assert strict_tool["function"]["parameters"]["required"] == ["user_id"]


@pytest.mark.asyncio
async def test_chat_json_mode_detection(mock_litellm):
    provider = LiteLLMProvider(
        api_key="test-key",
        default_model="gpt-4o",
        enforce_strict_tools=True,
    )

    # Mock capabilities to support JSON
    provider.get_capabilities = MagicMock(return_value={
        "vision": False,
        "tools": True,
        "json": True,
        "context_size": 128000,
        "prompt_caching": False,
    })

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content='{"name": "test"}', tool_calls=[]), finish_reason="stop")
    ]

    with patch("amberclaw.providers.litellm_provider.acompletion", new_callable=AsyncMock) as mock_acompletion:
        mock_acompletion.return_value = mock_response

        # Scenario 1: Keyword detection in prompt
        messages = [{"role": "user", "content": "Return the user as a JSON object."}]
        await provider.chat(messages=messages)

        called_kwargs = mock_acompletion.call_args[1]
        assert called_kwargs.get("response_format") == {"type": "json_object"}

        # Scenario 2: Explicit response_format parameter passed
        messages_no_kw = [{"role": "user", "content": "Get user details."}]
        await provider.chat(messages=messages_no_kw, response_format={"type": "json_object"})

        called_kwargs_explicit = mock_acompletion.call_args[1]
        assert called_kwargs_explicit.get("response_format") == {"type": "json_object"}


@pytest.mark.asyncio
async def test_chat_strict_tool_enforcement(mock_litellm):
    provider = LiteLLMProvider(
        api_key="test-key",
        default_model="gpt-4o",
        enforce_strict_tools=True,
    )

    # Mock capabilities to support JSON
    provider.get_capabilities = MagicMock(return_value={
        "vision": False,
        "tools": True,
        "json": True,
        "context_size": 128000,
        "prompt_caching": False,
    })

    tools = [{
        "type": "function",
        "function": {
            "name": "query_db",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string"},
                },
            },
        },
    }]

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="Hello", tool_calls=[]), finish_reason="stop")
    ]

    with patch("amberclaw.providers.litellm_provider.acompletion", new_callable=AsyncMock) as mock_acompletion:
        mock_acompletion.return_value = mock_response

        # Scenario: Tools are passed, enforce_strict_tools is True
        messages = [{"role": "user", "content": "Execute sql query"}]
        await provider.chat(messages=messages, tools=tools)

        called_kwargs = mock_acompletion.call_args[1]
        # Verify strict is enabled and additionalProperties is False
        called_tools = called_kwargs.get("tools")
        assert called_tools is not None
        assert called_tools[0]["function"]["strict"] is True
        assert called_tools[0]["function"]["parameters"]["additionalProperties"] is False
        assert called_tools[0]["function"]["parameters"]["required"] == ["sql"]
        # When tools are active, response_format should not be JSON object to avoid API conflicts
        assert called_kwargs.get("response_format") is None
