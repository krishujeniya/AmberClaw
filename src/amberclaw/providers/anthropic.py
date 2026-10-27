"""Anthropic Claude LLM provider implementation."""

from amberclaw.providers.litellm_provider import LiteLLMProvider


class AnthropicProvider(LiteLLMProvider):
    """Direct provider interface for Anthropic Claude models."""

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "anthropic/claude-3-5-sonnet-20241022",
        **kwargs,
    ) -> None:
        super().__init__(
            api_key=api_key,
            api_base=api_base,
            default_model=default_model,
            provider_name="anthropic",
            **kwargs,
        )

    def get_default_model(self) -> str:
        return self.default_model
