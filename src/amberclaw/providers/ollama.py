"""Ollama local inference provider implementation."""

from amberclaw.providers.litellm_provider import LiteLLMProvider


class OllamaProvider(LiteLLMProvider):
    """Direct provider interface for local Ollama instances."""

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = "http://localhost:11434",
        default_model: str = "ollama/llama3.2",
        **kwargs,
    ) -> None:
        super().__init__(
            api_key=api_key or "ollama",
            api_base=api_base,
            default_model=default_model,
            provider_name="ollama",
            **kwargs,
        )

    def get_default_model(self) -> str:
        return self.default_model
