# ruff: noqa: PLR2004
"""Unit tests for AmberClaw LLM Providers registry, catalog, and contracts."""

from amberclaw.providers.base import LLMResponse, ToolCallRequest
from amberclaw.providers.capabilities import detect_capabilities
from amberclaw.providers.catalog import (
    validate_model_name,
)
from amberclaw.providers.registry import (
    PROVIDERS,
    ProviderSpec,
    find_by_model,
    find_by_name,
    find_gateway,
)

# ==============================================================================
# 1. Provider Registry Lookup
# ==============================================================================


def test_provider_registry_contains_major_providers():
    names = {p.name for p in PROVIDERS}
    assert "openai" in names
    assert "anthropic" in names
    assert "gemini" in names
    assert "deepseek" in names
    assert "openrouter" in names
    assert "ollama" in names


def test_find_by_name():
    openai_spec = find_by_name("openai")
    assert openai_spec is not None
    assert isinstance(openai_spec, ProviderSpec)
    assert openai_spec.name == "openai"
    assert "OPENAI_API_KEY" in openai_spec.env_key

    anthropic_spec = find_by_name("anthropic")
    assert anthropic_spec is not None
    assert anthropic_spec.name == "anthropic"

    assert find_by_name("non_existent_provider_xyz") is None


def test_find_by_model_matching():
    gpt4_spec = find_by_model("gpt-4o")
    assert gpt4_spec is not None
    assert gpt4_spec.name == "openai"

    claude_spec = find_by_model("claude-3-5-sonnet-20241022")
    assert claude_spec is not None
    assert claude_spec.name == "anthropic"

    gemini_spec = find_by_model("gemini-1.5-pro")
    assert gemini_spec is not None
    assert gemini_spec.name == "gemini"


def test_find_gateway_detection():
    # Detect OpenRouter by key prefix
    gw_by_key = find_gateway(api_key="sk-or-v1-abcdef123456")
    assert gw_by_key is not None
    assert gw_by_key.name == "openrouter"
    assert gw_by_key.is_gateway is True

    # Detect by provider_name
    gw_by_name = find_gateway(provider_name="openrouter")
    assert gw_by_name is not None
    assert gw_by_name.name == "openrouter"

    # Detect local vLLM by api_base
    gw_local = find_gateway(api_base="http://localhost:8000/v1")
    # Should not match standard provider unless configured
    assert gw_local is None or gw_local.is_local or gw_local.is_gateway


# ==============================================================================
# 2. Model Catalog & Capability Detection
# ==============================================================================


def test_model_catalog_validation():
    # Valid canonical model
    res_gpt4 = validate_model_name("gpt-4o")
    assert res_gpt4.is_valid is True
    assert res_gpt4.canonical_name == "gpt-4o"
    assert res_gpt4.provider == "openai"

    # Alias resolution
    res_alias = validate_model_name("claude-3.5-sonnet")
    assert res_alias.is_valid is True
    assert res_alias.canonical_name == "claude-3-5-sonnet-20241022"

    # Fuzzy match on typo
    res_typo = validate_model_name("gpt-4-turrbo")
    assert res_typo.is_valid is False
    assert len(res_typo.suggested_alternatives) > 0


def test_detect_capabilities():
    cap = detect_capabilities("gpt-4o", provider="openai")
    assert cap.model == "gpt-4o"
    assert cap.tools is True
    assert cap.streaming is True
    assert cap.context_window >= 4096


# ==============================================================================
# 3. Base Provider Contracts & Data Structures
# ==============================================================================


def test_tool_call_request_model():
    call = ToolCallRequest(
        id="call_999",
        name="web_search",
        arguments={"query": "pytest fixtures"},
    )
    assert call.id == "call_999"
    assert call.name == "web_search"
    assert call.arguments["query"] == "pytest fixtures"


def test_llm_response_model():
    call = ToolCallRequest(
        id="call_1",
        name="read_file",
        arguments={"path": "main.py"},
    )
    resp = LLMResponse(
        content="I will inspect the file now.",
        tool_calls=[call],
        usage={"prompt_tokens": 50, "completion_tokens": 12, "total_tokens": 62},
    )

    assert resp.content == "I will inspect the file now."
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "read_file"
    assert resp.usage["total_tokens"] == 62
