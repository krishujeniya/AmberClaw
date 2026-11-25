"""Offline regressions for provider protocol and untrusted SDK response shapes."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from amberclaw.providers.azure_openai_provider import AzureOpenAIProvider
from amberclaw.providers.custom_provider import CustomProvider
from amberclaw.providers.errors import _extract_status_code
from amberclaw.providers.litellm_client import LLMRouter
from amberclaw.providers.litellm_provider import LiteLLMProvider
from amberclaw.providers.openai_codex_provider import OpenAICodexProvider
from amberclaw.providers.transcription import (
    GroqTranscriptionProvider,
    OpenAITranscriptionProvider,
)


@pytest.mark.parametrize(
    "provider_type", [CustomProvider, AzureOpenAIProvider, OpenAICodexProvider]
)
@pytest.mark.asyncio
async def test_chat_retry_accepts_shared_callback(provider_type):
    if provider_type is AzureOpenAIProvider:
        provider = provider_type(api_key="fixture", api_base="https://fixture.invalid")
    else:
        provider = provider_type()
    callback = AsyncMock()
    sdk_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="hello", tool_calls=[]),
                finish_reason="stop",
            )
        ],
        usage=None,
    )
    http_response = MagicMock(status_code=200)
    http_response.json.return_value = {
        "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}]
    }
    http_client = MagicMock()
    http_client.__aenter__.return_value.post = AsyncMock(return_value=http_response)
    with (
        patch("amberclaw.providers.custom_provider.AsyncOpenAI"),
        patch(
            "amberclaw.providers.azure_openai_provider.httpx.AsyncClient",
            return_value=http_client,
        ),
        patch(
            "amberclaw.providers.openai_codex_provider.get_codex_token",
            return_value=SimpleNamespace(account_id="fixture", access="fixture"),
        ),
        patch(
            "amberclaw.providers.openai_codex_provider._request_codex",
            new=AsyncMock(return_value=("hello", [], "stop")),
        ),
    ):
        if isinstance(provider, CustomProvider):
            provider._client.chat.completions.create = AsyncMock(
                return_value=sdk_response
            )
        result = await provider.chat_with_retry(
            [{"role": "user", "content": "hello"}], on_token=callback
        )
    assert result.content == "hello"
    callback.assert_awaited_once_with("hello")


@pytest.mark.asyncio
async def test_custom_restores_secret_before_callback():
    provider = CustomProvider(api_key="vault://fixture")
    provider._client.chat.completions.create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="hello", tool_calls=[]),
                    finish_reason="stop",
                )
            ],
            usage=None,
        )
    )
    observed_keys = []

    async def callback(_text):
        observed_keys.append(provider._client.api_key)

    with patch(
        "amberclaw.security.vault.vault.resolve_secret", return_value="resolved-fixture"
    ):
        await provider.chat([], on_token=callback)
    assert observed_keys == ["vault://fixture"]


@pytest.mark.parametrize("status", ["429", None, {}, []])
def test_malformed_response_status_is_not_a_status_code(status):
    assert (
        _extract_status_code(
            SimpleNamespace(response=SimpleNamespace(status_code=status))
        )
        is None
    )


@pytest.mark.parametrize(
    "provider_type", [GroqTranscriptionProvider, OpenAITranscriptionProvider]
)
@pytest.mark.parametrize("payload", [{"text": None}, {"text": 123}, {"text": []}, []])
@pytest.mark.asyncio
async def test_transcription_returns_only_strings(provider_type, payload, tmp_path):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fixture")
    response = MagicMock()
    response.json.return_value = payload
    client = MagicMock()
    client.__aenter__.return_value.post = AsyncMock(return_value=response)
    with patch(
        "amberclaw.providers.transcription.httpx.AsyncClient", return_value=client
    ):
        assert await provider_type(api_key="fixture").transcribe(audio) == ""


@pytest.mark.asyncio
async def test_router_normalizes_empty_text():
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None))]
    )
    with patch(
        "amberclaw.providers.litellm_client.acompletion",
        new=AsyncMock(return_value=response),
    ):
        assert await LLMRouter(default_model="fixture-empty-text").generate([]) == ""


@pytest.mark.asyncio
async def test_router_reports_missing_optional_dependency():
    with (
        patch("amberclaw.providers.litellm_client.acompletion", None),
        pytest.raises(RuntimeError, match=r"[Ll]ite[Ll][Ll][Mm].*not installed"),
    ):
        await LLMRouter().generate([])


def test_cache_breakpoint_preserves_empty_text_marker():
    provider = LiteLLMProvider()
    messages = [
        {"role": "user", "content": ""},
        {"role": "assistant", "content": "answer"},
    ]
    cached, _tools = provider._apply_cache_control(messages, None)
    assert cached[0]["content"] == [
        {"type": "text", "text": "", "cache_control": {"type": "ephemeral"}}
    ]
    assert messages[0]["content"] == ""
