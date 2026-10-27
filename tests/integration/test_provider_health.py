import logging
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from amberclaw.api.main import app
from amberclaw.api.auth import create_access_token
from amberclaw.providers.litellm_client import LLMRouter, LLMMessage


@pytest.fixture
def auth_headers():
    token = create_access_token({"sub": "admin", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


def test_provider_health_endpoint(auth_headers, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-12345")
    client = TestClient(app)

    response = client.get("/api/v1/providers/health", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert "engine" in data

    providers = {p["provider"]: p for p in data["providers"]}
    assert "openai" in providers
    assert providers["openai"]["configured"] is True
    assert providers["openai"]["status"] == "configured"
    assert "anthropic" in providers


@pytest.mark.asyncio
async def test_llm_router_token_cost_tracking(caplog):
    caplog.set_level(logging.INFO)
    router = LLMRouter()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hello world from test"

    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 15
    mock_usage.completion_tokens = 8
    mock_usage.total_tokens = 23
    mock_response.usage = mock_usage

    with patch("amberclaw.providers.litellm_client.acompletion", new_callable=AsyncMock) as mock_acomp:
        mock_acomp.return_value = mock_response

        messages = [LLMMessage(role="user", content="Hello")]
        result = await router.generate(messages=messages, model="gpt-4o")

        assert result == "Hello world from test"
        assert "LLM Token Usage [gpt-4o]: prompt=15, completion=8, total=23" in caplog.text
