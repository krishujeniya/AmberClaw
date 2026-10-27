"""AWS Bedrock foundation model provider implementation."""

from amberclaw.providers.litellm_provider import LiteLLMProvider


class BedrockProvider(LiteLLMProvider):
    """Direct provider interface for AWS Bedrock models."""

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0",
        **kwargs,
    ) -> None:
        super().__init__(
            api_key=api_key,
            api_base=api_base,
            default_model=default_model,
            provider_name="bedrock",
            **kwargs,
        )

    def get_default_model(self) -> str:
        return self.default_model
