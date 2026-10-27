"""Secure LLM provider credential management, environment discovery, and key masking."""

import os
from typing import ClassVar

from loguru import logger
from pydantic import BaseModel, Field

MIN_MASK_LENGTH: int = 8


class ProviderCredential(BaseModel):
    """Access credentials and endpoint configuration for an LLM provider."""

    provider: str
    api_key: str | None = Field(default=None, repr=False)
    api_base: str | None = None
    organization: str | None = None

    @property
    def is_configured(self) -> bool:
        """Return True if an API key or custom endpoint is available."""
        return bool(self.api_key or self.api_base)

    @property
    def masked_key(self) -> str:
        """Return safe masked representation of the API key for logs and audit trails."""
        if not self.api_key:
            return "[NOT SET]"
        if len(self.api_key) <= MIN_MASK_LENGTH:
            return "***"
        return f"{self.api_key[:4]}...{self.api_key[-4:]}"


class InferenceCredentialManager:
    """Manages credentials for LLM providers with automatic environment variable resolution."""

    ENV_MAPPINGS: ClassVar[dict[str, list[str]]] = {
        "openai": ["OPENAI_API_KEY"],
        "anthropic": ["ANTHROPIC_API_KEY"],
        "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        "groq": ["GROQ_API_KEY"],
        "deepseek": ["DEEPSEEK_API_KEY"],
        "mistral": ["MISTRAL_API_KEY"],
        "cohere": ["COHERE_API_KEY"],
        "openrouter": ["OPENROUTER_API_KEY"],
        "azure": ["AZURE_OPENAI_API_KEY", "AZURE_API_KEY"],
        "ollama": ["OLLAMA_HOST", "OLLAMA_BASE_URL"],
    }

    def __init__(self) -> None:
        self._credentials: dict[str, ProviderCredential] = {}
        self._load_from_environment()

    def _load_from_environment(self) -> None:
        """Discover credentials from standard provider environment variables."""
        for provider, env_keys in self.ENV_MAPPINGS.items():
            for env_key in env_keys:
                val = os.environ.get(env_key)
                if val:
                    if provider == "ollama":
                        self._credentials[provider] = ProviderCredential(
                            provider=provider,
                            api_base=val,
                        )
                    else:
                        self._credentials[provider] = ProviderCredential(
                            provider=provider,
                            api_key=val,
                        )
                    break

    def set_credential(
        self,
        provider: str,
        api_key: str | None = None,
        api_base: str | None = None,
        organization: str | None = None,
    ) -> ProviderCredential:
        """Explicitly set or override provider credentials at runtime."""
        p_norm = provider.lower()
        cred = ProviderCredential(
            provider=p_norm,
            api_key=api_key,
            api_base=api_base,
            organization=organization,
        )
        self._credentials[p_norm] = cred
        logger.info(
            "Configured credential for provider '{}' (masked: {})",
            p_norm,
            cred.masked_key,
        )
        return cred

    def get_credential(self, provider: str) -> ProviderCredential | None:
        """Retrieve stored credential for a provider."""
        return self._credentials.get(provider.lower())

    def has_credential(self, provider: str) -> bool:
        """Check whether valid credentials exist for a provider."""
        cred = self.get_credential(provider)
        return cred is not None and cred.is_configured

    def list_configured_providers(self) -> list[str]:
        """Return names of all providers currently equipped with valid credentials."""
        return [
            provider
            for provider, cred in self._credentials.items()
            if cred.is_configured
        ]
