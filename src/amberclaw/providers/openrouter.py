"""OpenRouter unified model aggregator provider implementation."""

from amberclaw.providers.litellm_provider import LiteLLMProvider


class OpenRouterProvider(LiteLLMProvider):
    """Direct provider interface for OpenRouter model gateway."""

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "openrouter/auto",
        **kwargs,
    ) -> None:
        super().__init__(
            api_key=api_key,
            api_base=api_base,
            default_model=default_model,
            provider_name="openrouter",
            **kwargs,
        )

    def get_default_model(self) -> str:
        return self.default_model
