"""DeepSeek LLM and reasoning provider implementation."""

from amberclaw.providers.litellm_provider import LiteLLMProvider


class DeepSeekProvider(LiteLLMProvider):
    """Direct provider interface for DeepSeek models."""

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "deepseek/deepseek-chat",
        **kwargs,
    ) -> None:
        super().__init__(
            api_key=api_key,
            api_base=api_base,
            default_model=default_model,
            provider_name="deepseek",
            **kwargs,
        )

    def get_default_model(self) -> str:
        return self.default_model
