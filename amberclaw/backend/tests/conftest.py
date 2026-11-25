import os
import secrets
from unittest.mock import MagicMock, patch

import pytest

from amberclaw.api.middleware import RateLimiterMiddleware

_TEST_JWT_SECRET = secrets.token_urlsafe(48)
_TEST_CLIENT_SECRET = secrets.token_urlsafe(48)


@pytest.fixture(autouse=True)
def configure_test_auth(monkeypatch):
    """Explicit ephemeral test configuration; production has no default secret."""
    monkeypatch.setenv("JWT_SECRET_KEY", _TEST_JWT_SECRET)
    monkeypatch.setenv("AUTH_CLIENT_ID", "offline-admin")
    monkeypatch.setenv("AUTH_CLIENT_SECRET", _TEST_CLIENT_SECRET)


@pytest.fixture(autouse=True)
def mock_litellm_if_offline():
    if os.environ.get("MOCK_LLM") == "true":
        with patch("amberclaw.agent.provider.litellm_completion") as mock_completion:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[
                0
            ].message.content = "This is a mock response from LiteLLM."
            mock_completion.return_value = mock_response
            yield mock_completion
    else:
        yield


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    RateLimiterMiddleware.reset_all()
    yield
    RateLimiterMiddleware.reset_all()
