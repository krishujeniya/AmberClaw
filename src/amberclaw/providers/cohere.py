"""Cohere Command LLM provider implementation."""

from amberclaw.providers.litellm_provider import LiteLLMProvider


class CohereProvider(LiteLLMProvider):
    """Direct provider interface for Cohere Command models."""

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "cohere/command-r-plus",
        **kwargs,
    ) -> None:
        super().__init__(
            api_key=api_key,
            api_base=api_base,
            default_model=default_model,
            provider_name="cohere",
            **kwargs,
        )

    def get_default_model(self) -> str:
        return self.default_model
