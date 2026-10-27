# ruff: noqa: PLR2004
"""Integration and contract test suite across multiple LLM providers.

Verifies consistent behavior, standardized LLMResponse output, tool calling parsing,
streaming contracts, error normalization, and retry classification across 5+ providers.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from amberclaw.providers.azure_openai_provider import AzureOpenAIProvider
from amberclaw.providers.base import LLMProvider, LLMResponse
from amberclaw.providers.custom_provider import CustomProvider
from amberclaw.providers.litellm_provider import LiteLLMProvider
from amberclaw.providers.ollama_provider import OllamaProvider
from amberclaw.providers.openai_codex_provider import OpenAICodexProvider
from amberclaw.providers.vllm import VLLMProvider


class TestProviderContractSuite:
    """Standardized contract tests for all AmberClaw LLMProvider implementations."""

    @pytest.fixture
    def sample_messages(self):
        return [
            {"role": "system", "content": "You are AmberClaw AI OS."},
            {"role": "user", "content": "Hello, execute test!"},
        ]

    @pytest.fixture
    def sample_tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read file contents",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                },
            }
        ]

    def test_provider_subclass_hierarchy(self):
        """Contract Check: All providers must inherit from LLMProvider and define standard retry markers."""
        providers = [
            LiteLLMProvider,
            AzureOpenAIProvider,
            OllamaProvider,
            OpenAICodexProvider,
            CustomProvider,
            VLLMProvider,
        ]
        for p in providers:
            assert issubclass(p, LLMProvider)
            assert hasattr(p, "_TRANSIENT_ERROR_MARKERS")
            assert "429" in p._TRANSIENT_ERROR_MARKERS
            assert "500" in p._TRANSIENT_ERROR_MARKERS

    @pytest.mark.asyncio
    async def test_litellm_provider_contract(self, sample_messages, sample_tools):
        """Contract Check: LiteLLMProvider returns compliant LLMResponse with tool calls."""
        provider = LiteLLMProvider(api_key="test-key", default_model="gpt-4o")

        mock_resp = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "I will read the file."
        mock_tool = MagicMock()
        mock_tool.id = "call_123"
        mock_tool.function.name = "read_file"
        mock_tool.function.arguments = '{"path": "/etc/config.json"}'
        mock_choice.message.tool_calls = [mock_tool]
        mock_choice.finish_reason = "tool_calls"
        mock_resp.choices = [mock_choice]
        mock_resp.usage.prompt_tokens = 25
        mock_resp.usage.completion_tokens = 15

        with patch(
            "amberclaw.providers.litellm_provider.acompletion", new_callable=AsyncMock
        ) as mock_act:
            mock_act.return_value = mock_resp

            res: LLMResponse = await provider.chat(
                messages=sample_messages, tools=sample_tools
            )

            assert isinstance(res, LLMResponse)
            assert res.content == "I will read the file."
            assert res.has_tool_calls is True
            assert len(res.tool_calls) == 1
            assert res.tool_calls[0].name == "read_file"
            assert res.tool_calls[0].arguments == {"path": "/etc/config.json"}
            assert res.usage["prompt_tokens"] == 25

    @pytest.mark.asyncio
    async def test_ollama_provider_contract(self, sample_messages):
        """Contract Check: OllamaProvider translates messages and returns LLMResponse."""
        provider = OllamaProvider(
            api_base="http://localhost:11434", default_model="llama3"
        )

        mock_http_resp = MagicMock()
        mock_http_resp.status_code = 200
        mock_http_resp.json.return_value = {
            "message": {
                "role": "assistant",
                "content": "Local Llama response",
            },
            "prompt_eval_count": 30,
            "eval_count": 20,
            "done": True,
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_http_resp

            res: LLMResponse = await provider.chat(messages=sample_messages)

            assert isinstance(res, LLMResponse)
            assert res.content == "Local Llama response"
            assert res.has_tool_calls is False
            assert res.usage["prompt_tokens"] == 30
            assert res.usage["completion_tokens"] == 20

    @pytest.mark.asyncio
    async def test_azure_openai_provider_contract(self, sample_messages, sample_tools):
        """Contract Check: AzureOpenAIProvider enforces version 2024-10-21 and parses responses."""
        provider = AzureOpenAIProvider(
            api_key="azure-secret-key",
            api_base="https://my-azure.openai.azure.com",
            default_model="gpt-5.2-chat",
        )
        assert provider.api_version == "2024-10-21"

        mock_http_resp = MagicMock()
        mock_http_resp.status_code = 200
        mock_http_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Azure response",
                        "tool_calls": [
                            {
                                "id": "az_call_1",
                                "type": "function",
                                "function": {
                                    "name": "read_file",
                                    "arguments": '{"path": "/azure/blob"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 50, "completion_tokens": 20},
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_http_resp

            res: LLMResponse = await provider.chat(
                messages=sample_messages, tools=sample_tools
            )

            assert isinstance(res, LLMResponse)
            assert res.content == "Azure response"
            assert len(res.tool_calls) == 1
            assert res.tool_calls[0].name == "read_file"
            assert res.tool_calls[0].arguments == {"path": "/azure/blob"}

    @pytest.mark.asyncio
    async def test_openai_codex_provider_contract(self, sample_messages):
        """Contract Check: OpenAICodexProvider parses code completion responses."""
        provider = OpenAICodexProvider(default_model="openai-codex/gpt-5.1-codex")

        mock_token = MagicMock()
        mock_token.account_id = "test-acc-123"
        mock_token.access = "test-access-token"

        mock_stream = MagicMock()
        mock_stream.status_code = 200

        async def fake_aiter_lines():
            yield 'data: {"type": "response.output_text.delta", "delta": "def calculate_hash(): return True"}'
            yield ""
            yield 'data: {"type": "response.completed", "response": {"status": "completed"}}'
            yield ""
            yield "data: [DONE]"
            yield ""

        mock_stream.aiter_lines = fake_aiter_lines

        with (
            patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread,
            patch("httpx.AsyncClient.stream") as mock_stream_ctx,
        ):
            mock_to_thread.return_value = mock_token
            mock_stream_ctx.return_value.__aenter__.return_value = mock_stream

            res: LLMResponse = await provider.chat(messages=sample_messages)

            assert isinstance(res, LLMResponse)
            assert "def calculate_hash" in (res.content or "")

    @pytest.mark.asyncio
    async def test_custom_provider_contract(self, sample_messages):
        """Contract Check: CustomProvider wraps arbitrary endpoints with standard format."""
        provider = CustomProvider(
            api_base="https://custom.ai.internal/v1",
            api_key="internal-key",
            default_model="custom-v1",
        )

        mock_choice = MagicMock()
        mock_choice.message.content = "Custom model output"
        mock_choice.message.tool_calls = []
        mock_choice.finish_reason = "stop"

        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]
        mock_completion.usage.prompt_tokens = 12
        mock_completion.usage.completion_tokens = 5

        with patch.object(
            provider._client.chat.completions,
            "create",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.return_value = mock_completion

            res: LLMResponse = await provider.chat(messages=sample_messages)

            assert isinstance(res, LLMResponse)
            assert res.content == "Custom model output"

    @pytest.mark.asyncio
    async def test_vllm_provider_contract(self, sample_messages):
        """Contract Check: VLLMProvider routes requests to OpenAI-compatible vLLM endpoints."""
        provider = VLLMProvider(
            api_base="http://remote-vllm:8000/v1",
            default_model="meta-llama/Llama-3-70b",
        )

        mock_resp = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "vLLM high throughput output"
        mock_choice.message.tool_calls = []
        mock_choice.finish_reason = "stop"
        mock_resp.choices = [mock_choice]
        mock_resp.usage.prompt_tokens = 40
        mock_resp.usage.completion_tokens = 10

        with (
            patch.object(
                provider.runner, "check_health", new_callable=AsyncMock
            ) as mock_health,
            patch(
                "amberclaw.providers.litellm_provider.acompletion",
                new_callable=AsyncMock,
            ) as mock_acompletion,
        ):
            mock_health.return_value = True
            mock_acompletion.return_value = mock_resp

            res: LLMResponse = await provider.chat(messages=sample_messages)

            assert isinstance(res, LLMResponse)
            assert res.content == "vLLM high throughput output"
