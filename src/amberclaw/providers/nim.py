"""NVIDIA NIM microservice LLM provider implementation."""

from amberclaw.providers.litellm_provider import LiteLLMProvider


class NIMProvider(LiteLLMProvider):
    """Direct provider interface for NVIDIA NIM microservice endpoints."""

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "nim/meta/llama-3.1-70b-instruct",
        **kwargs,
    ) -> None:
        super().__init__(
            api_key=api_key,
            api_base=api_base,
            default_model=default_model,
            provider_name="nim",
            **kwargs,
        )

    def get_default_model(self) -> str:
        return self.default_model
