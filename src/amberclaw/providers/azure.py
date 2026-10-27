"""Microsoft Azure OpenAI LLM provider implementation."""

from amberclaw.providers.litellm_provider import LiteLLMProvider


class AzureProvider(LiteLLMProvider):
    """Direct provider interface for Azure OpenAI deployments."""

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "azure/gpt-4o",
        **kwargs,
    ) -> None:
        super().__init__(
            api_key=api_key,
            api_base=api_base,
            default_model=default_model,
            provider_name="azure",
            **kwargs,
        )

    def get_default_model(self) -> str:
        return self.default_model
