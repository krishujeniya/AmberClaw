"""Unit tests verifying all LLM provider wrappers instantiate with valid default models."""

from amberclaw.providers.anthropic import AnthropicProvider
from amberclaw.providers.azure import AzureProvider
from amberclaw.providers.bedrock import BedrockProvider
from amberclaw.providers.cohere import CohereProvider
from amberclaw.providers.deepseek import DeepSeekProvider
from amberclaw.providers.gemini import GeminiProvider
from amberclaw.providers.groq import GroqProvider
from amberclaw.providers.mistral import MistralProvider
from amberclaw.providers.nim import NIMProvider
from amberclaw.providers.ollama import OllamaProvider
from amberclaw.providers.openai import OpenAIProvider
from amberclaw.providers.openrouter import OpenRouterProvider
from amberclaw.providers.xai import XAIProvider


def test_provider_instantiations():
    providers = [
        (AnthropicProvider(api_key="test"), "claude"),
        (OpenAIProvider(api_key="test"), "gpt-4o"),
        (GeminiProvider(api_key="test"), "gemini"),
        (GroqProvider(api_key="test"), "groq"),
        (DeepSeekProvider(api_key="test"), "deepseek"),
        (MistralProvider(api_key="test"), "mistral"),
        (CohereProvider(api_key="test"), "cohere"),
        (OpenRouterProvider(api_key="test"), "openrouter"),
        (BedrockProvider(api_key="test"), "bedrock"),
        (AzureProvider(api_key="test"), "azure"),
        (OllamaProvider(api_key="test"), "ollama"),
        (NIMProvider(api_key="test"), "nim"),
        (XAIProvider(api_key="test"), "xai"),
    ]

    for p, expected_substring in providers:
        default_model = p.get_default_model()
        assert expected_substring in default_model.lower()
