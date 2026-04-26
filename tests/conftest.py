import os
import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture(autouse=True)
def mock_litellm_if_offline():
    if os.environ.get("MOCK_LLM") == "true":
        with patch("amberclaw.agent.provider.litellm_completion") as mock_completion:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "This is a mock response from LiteLLM."
            mock_completion.return_value = mock_response
            yield mock_completion
    else:
        yield
