"""Groq high-speed LPU inference provider implementation."""

from amberclaw.providers.litellm_provider import LiteLLMProvider


class GroqProvider(LiteLLMProvider):
    """Direct provider interface for Groq LPU accelerated inference."""

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "groq/llama-3.3-70b-versatile",
        **kwargs,
    ) -> None:
        super().__init__(
            api_key=api_key,
            api_base=api_base,
            default_model=default_model,
            provider_name="groq",
            **kwargs,
        )

    def get_default_model(self) -> str:
        return self.default_model
