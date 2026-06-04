import os
import pytest
from pathlib import Path
from unittest.mock import AsyncMock
from amberclaw.providers.litellm_provider import LiteLLMProvider
from amberclaw.security.vault import vault as global_vault


@pytest.mark.asyncio
async def test_dynamic_credential_proxy_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that LiteLLMProvider dynamic credential proxy resolution behaves correctly."""
    # Point global vault to temporary path
    monkeypatch.setattr(global_vault, "base_dir", tmp_path)
    monkeypatch.setattr(global_vault, "key_file", tmp_path / ".vault_key")
    monkeypatch.setattr(global_vault, "vault_file", tmp_path / "vault.enc")
    monkeypatch.setattr(global_vault, "_fernet", None)

    # Store a dummy credential in the vault
    secret_key = "sk-super-duper-secret-12345"
    global_vault.store_secret("providers/openai/api_key", secret_key)

    # Ensure clean environment
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert "OPENAI_API_KEY" not in os.environ

    # Initialize provider with vault reference
    provider = LiteLLMProvider(
        api_key="vault://providers/openai/api_key",
        api_base="https://api.openai.com/v1",
        default_model="openai/gpt-4o",
    )

    # Reference must remain unresolved on the class instance
    assert provider.api_key == "vault://providers/openai/api_key"
    assert "OPENAI_API_KEY" not in os.environ

    # Mock acompletion to inspect what parameters it receives, and check active env vars
    mock_acompletion = AsyncMock()

    class DummyChoice:
        class DummyMessage:
            content = "Hello response"
            tool_calls = None
        message = DummyMessage()
        finish_reason = "stop"

    class DummyResponse:
        choices = [DummyChoice()]

    mock_acompletion.return_value = DummyResponse()
    monkeypatch.setattr("amberclaw.providers.litellm_provider.acompletion", mock_acompletion)

    # Perform the chat execution
    messages = [{"role": "user", "content": "hello"}]
    res = await provider.chat(messages, model="openai/gpt-4o")

    # Verify the execution succeeded and returns expected content
    assert res.content == "Hello response"

    # Verify acompletion received the resolved secret key
    assert mock_acompletion.call_count == 1
    passed_args, passed_kwargs = mock_acompletion.call_args
    assert passed_kwargs["api_key"] == secret_key

    # Verify environment variables were cleaned up afterwards
    assert "OPENAI_API_KEY" not in os.environ
