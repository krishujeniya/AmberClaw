"""OpenAI LLM provider implementation."""

from amberclaw.providers.litellm_provider import LiteLLMProvider


class OpenAIProvider(LiteLLMProvider):
    """Direct provider interface for OpenAI GPT and o-series reasoning models."""

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "openai/gpt-4o",
        **kwargs,
    ) -> None:
        super().__init__(
            api_key=api_key,
            api_base=api_base,
            default_model=default_model,
            provider_name="openai",
            **kwargs,
        )

    def get_default_model(self) -> str:
        return self.default_model
