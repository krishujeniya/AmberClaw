# ruff: noqa: PLR2004, ARG002
"""Comprehensive tests for Section 3 upgrades:
- ProviderCapability contract
- Model catalog validation and fuzzy matching
- Error normalization and retry eligibility
- Circuit breaker and dynamic health scoring
- Cost-aware and latency-aware intelligent routing
- Model deprecation schedule
- Streamed vs non-streamed response parity
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from amberclaw.providers.base import LLMProvider, LLMResponse
from amberclaw.providers.capabilities import ProviderCapability, detect_capabilities
from amberclaw.providers.catalog import validate_model_name
from amberclaw.providers.deprecations import check_model_deprecation
from amberclaw.providers.errors import (
    AuthenticationError,
    ContextWindowExceededError,
    InvalidRequestError,
    ModelNotFoundError,
    ProviderServerError,
    ProviderTimeoutError,
    RateLimitError,
    normalize_provider_error,
)
from amberclaw.providers.litellm_provider import LiteLLMProvider
from amberclaw.providers.resilience import (
    CircuitBreaker,
    CircuitState,
    ProviderHealthTracker,
    get_circuit_breaker,
)
from amberclaw.providers.router import (
    ModelRouter,
    RoutingRequirement,
    RoutingStrategy,
)

# ==============================================================================
# 1. ProviderCapability Contract
# ==============================================================================


def test_provider_capability_contract_fields():
    cap = ProviderCapability(
        model="gpt-4o",
        provider="openai",
        tools=True,
        json_mode=True,
        vision=True,
        audio=False,
        streaming=True,
        context_window=128000,
        max_output_tokens=16384,
        prompt_caching=True,
        reasoning=False,
        input_cost_per_token=0.0000025,
        output_cost_per_token=0.00001,
        pricing_source="test",
    )
    assert cap.model == "gpt-4o"
    assert cap.tools is True
    assert cap.json_mode is True
    assert cap.vision is True
    assert cap.audio is False
    assert cap.streaming is True
    assert cap.context_window == 128000
    assert cap.max_output_tokens == 16384
    assert cap.prompt_caching is True
    assert cap.reasoning is False
    assert cap.input_cost_per_token == 0.0000025
    assert cap.output_cost_per_token == 0.00001


def test_provider_capability_dict_compatibility_and_aliases():
    cap = ProviderCapability(
        model="claude-3-5-sonnet",
        context_window=200000,
        json_mode=True,
        tools=True,
        prompt_caching=True,
    )
    # Test dict-like indexing with legacy aliases
    assert cap["context_size"] == 200000
    assert cap["context_window"] == 200000
    assert cap["json"] is True
    assert cap["json_mode"] is True
    assert cap["tools"] is True
    assert cap["caching"] is True
    assert cap.get("vision", False) is False
    assert "context_size" in cap
    assert cap.to_dict()["context_size"] == 200000


def test_detect_capabilities_standard_models():
    claude = detect_capabilities("anthropic/claude-3-5-sonnet")
    assert claude.vision is True
    assert claude.context_window == 200000
    assert claude.prompt_caching is True
    assert claude.input_cost_per_token > 0.0

    r1 = detect_capabilities("deepseek/deepseek-r1")
    assert r1.reasoning is True
    assert r1.context_window == 64000


# ==============================================================================
# 2. Model Catalog Validation & Fuzzy Matching
# ==============================================================================


def test_catalog_validation_canonical():
    res = validate_model_name("gpt-4o", provider="openai")
    assert res.is_valid is True
    assert res.canonical_name == "gpt-4o"


def test_catalog_validation_aliases():
    res = validate_model_name("gpt4o")
    assert res.is_valid is True
    assert res.canonical_name == "gpt-4o"
    assert "alias" in (res.warning or "").lower()

    res_claude = validate_model_name("claude-3.5-sonnet")
    assert res_claude.is_valid is True
    assert "claude-3-5-sonnet" in res_claude.canonical_name


def test_catalog_validation_fuzzy_suggestions():
    # Misspelled model
    res = validate_model_name("gpt-40-miny", provider="openai")
    assert res.is_valid is False
    assert len(res.suggested_alternatives) > 0
    assert any("gpt-4o-mini" in alt for alt in res.suggested_alternatives)
    assert "Did you mean" in (res.warning or "")


def test_catalog_validation_custom_passthrough():
    res = validate_model_name("custom/my-internal-model")
    assert res.is_valid is True
    assert res.canonical_name == "my-internal-model"


# ==============================================================================
# 3. Error Normalization & Retry Eligibility
# ==============================================================================


def test_normalize_rate_limit_error():
    err_text = "429 Too Many Requests: Rate limit reached. Retry-After: 3.5s"
    norm = normalize_provider_error(err_text, provider="openai", model="gpt-4o")
    assert isinstance(norm, RateLimitError)
    assert norm.status_code == 429
    assert norm.is_retryable is True
    assert norm.retry_after_s == 3.5


def test_normalize_authentication_error():
    err_text = "401 Unauthorized: Invalid API key provided"
    norm = normalize_provider_error(err_text, provider="anthropic")
    assert isinstance(norm, AuthenticationError)
    assert norm.status_code == 401
    assert norm.is_retryable is False


def test_normalize_context_window_error():
    err_text = "BadRequestError: context_length_exceeded, maximum context length is 8192 tokens"
    norm = normalize_provider_error(err_text)
    assert isinstance(norm, ContextWindowExceededError)
    assert norm.is_retryable is False


def test_normalize_timeout_and_server_errors():
    t_err = normalize_provider_error("ReadTimeout: Request timed out after 30s")
    assert isinstance(t_err, ProviderTimeoutError)
    assert t_err.is_retryable is True

    s_err = normalize_provider_error(
        "503 Service Temporarily Unavailable / Server Overloaded"
    )
    assert isinstance(s_err, ProviderServerError)
    assert s_err.is_retryable is True

    not_found = normalize_provider_error(
        "404 Model does not exist or account lacks access"
    )
    assert isinstance(not_found, ModelNotFoundError)
    assert not_found.is_retryable is False

    invalid_req = normalize_provider_error(
        "400 Bad Request: unsupported parameter 'thinking'"
    )
    assert isinstance(invalid_req, InvalidRequestError)
    assert invalid_req.is_retryable is False


def test_base_provider_transient_error_integration():
    class DummyProvider(LLMProvider):
        async def chat(self, *args, **kwargs):
            return LLMResponse(content="ok")

        def get_default_model(self):
            return "dummy"

    # Verify that _is_transient_error uses normalized error classification
    assert DummyProvider._is_transient_error("429 rate limit exceeded") is True
    assert DummyProvider._is_transient_error("502 Bad Gateway") is True
    assert DummyProvider._is_transient_error("401 Unauthorized") is False
    assert DummyProvider._is_transient_error("context_length_exceeded") is False


# ==============================================================================
# 4. Circuit Breaker & Health Scoring
# ==============================================================================


def test_provider_health_tracker_scoring():
    tracker = ProviderHealthTracker(name="test_model", window_size=20)
    # Initially healthy
    assert tracker.compute_health_score(CircuitState.CLOSED) == 1.0

    # Record 10 successes with low latency
    for _ in range(10):
        tracker.record_call(True, latency_ms=120.0)
    assert tracker.compute_health_score(CircuitState.CLOSED) == 1.0

    # Record 3 failures
    for _ in range(3):
        tracker.record_call(False, latency_ms=500.0)
    # Health score should drop
    degraded = tracker.compute_health_score(CircuitState.CLOSED)
    assert degraded < 1.0
    assert degraded > 0.0

    # If circuit opens, score drops to 0.0
    assert tracker.compute_health_score(CircuitState.OPEN) == 0.0

    # If circuit in half_open, score capped at 0.5
    assert tracker.compute_health_score(CircuitState.HALF_OPEN) <= 0.5

    metrics = tracker.get_health_metrics()
    assert metrics["total_calls"] == 13
    assert metrics["total_failures"] == 3
    assert metrics["consecutive_failures"] == 3


@pytest.mark.asyncio
async def test_circuit_breaker_health_integration():
    cb = CircuitBreaker(name="test_cb_health", failure_threshold=2)
    assert cb.health_score == 1.0

    async def fail_coro():
        raise RuntimeError("simulated error")

    with pytest.raises(RuntimeError):
        await cb.call_async(fail_coro)

    assert cb.health_score < 1.0
    metrics = cb.get_health_metrics()
    assert metrics["total_failures"] == 1


# ==============================================================================
# 5. Cost-Aware and Latency-Aware Intelligent Routing
# ==============================================================================


def test_model_router_strategies():
    router = ModelRouter()
    candidates = [
        "openai/gpt-4o",  # High quality, medium cost ($2.5/Mtok)
        "openai/gpt-4o-mini",  # Low cost ($0.15/Mtok)
        "deepseek/deepseek-r1",  # Reasoning model
    ]

    # 1. Cost Optimized: gpt-4o-mini should win
    decision_cost = router.select_optimal_model(
        candidates=candidates,
        strategy=RoutingStrategy.COST_OPTIMIZED,
    )
    assert decision_cost.selected_model == "openai/gpt-4o-mini"
    assert decision_cost.strategy == RoutingStrategy.COST_OPTIMIZED

    # 2. Quality Optimized with reasoning requirement: deepseek-r1 should win
    decision_quality = router.select_optimal_model(
        candidates=candidates,
        requirements=RoutingRequirement(reasoning_required=True),
        strategy=RoutingStrategy.QUALITY_OPTIMIZED,
    )
    assert decision_quality.selected_model == "deepseek/deepseek-r1"

    # 3. Vision requirement: deepseek-r1 lacks vision, gpt-4o should be selected
    decision_vision = router.select_optimal_model(
        candidates=["deepseek/deepseek-r1", "openai/gpt-4o"],
        requirements=RoutingRequirement(vision_required=True),
        strategy=RoutingStrategy.BALANCED,
    )
    assert decision_vision.selected_model == "openai/gpt-4o"


def test_model_router_skips_open_circuits():
    router = ModelRouter()
    # Trip circuit for model A
    cb_a = get_circuit_breaker("llm_model_a", failure_threshold=1)
    cb_a.record_failure(RuntimeError("down"))
    assert cb_a.state == CircuitState.OPEN

    cb_b = get_circuit_breaker("llm_model_b")
    cb_b.reset()

    decision = router.select_optimal_model(
        candidates=["model_a", "model_b"],
        strategy=RoutingStrategy.BALANCED,
    )
    assert decision.selected_model == "model_b"


# ==============================================================================
# 6. Model Deprecation Registry
# ==============================================================================


def test_model_deprecations():
    notice = check_model_deprecation("openai/gpt-3.5-turbo-0613")
    assert notice is not None
    assert notice.is_deprecated is True
    assert notice.sunset_date == "2024-06-13"
    assert notice.replacement_model == "gpt-4o-mini"

    notice_claude = check_model_deprecation("anthropic/claude-2.0")
    assert notice_claude is not None
    assert notice_claude.replacement_model == "claude-3-5-sonnet-20241022"

    active = check_model_deprecation("openai/gpt-4o")
    assert active is None


# ==============================================================================
# 7. Streamed vs Non-Streamed Response Parity
# ==============================================================================


@pytest.mark.asyncio
async def test_streamed_vs_non_streamed_text_parity():
    provider = LiteLLMProvider(api_key="mock-key", default_model="gpt-4o")

    # Non-streamed mock
    mock_non_stream = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Parallel execution confirmed."
    mock_choice.message.tool_calls = []
    mock_choice.finish_reason = "stop"
    mock_choice.message.reasoning_content = None
    mock_non_stream.choices = [mock_choice]
    mock_non_stream.usage.prompt_tokens = 20
    mock_non_stream.usage.completion_tokens = 5
    mock_non_stream.usage.total_tokens = 25

    # Streamed mock yielding chunks
    async def fake_stream():
        tokens = ["Parallel ", "execution ", "confirmed."]
        for t in tokens:
            chunk = MagicMock()
            chunk_choice = MagicMock()
            chunk_choice.delta.content = t
            chunk_choice.delta.tool_calls = None
            chunk_choice.delta.reasoning_content = None
            chunk_choice.finish_reason = None
            chunk.choices = [chunk_choice]
            yield chunk

        # Final chunk
        final_chunk = MagicMock()
        final_choice = MagicMock()
        final_choice.delta.content = None
        final_choice.delta.tool_calls = None
        final_choice.delta.reasoning_content = None
        final_choice.finish_reason = "stop"
        final_chunk.choices = [final_choice]
        final_chunk.usage.prompt_tokens = 20
        final_chunk.usage.completion_tokens = 5
        final_chunk.usage.total_tokens = 25
        yield final_chunk

    with patch(
        "amberclaw.providers.litellm_provider.acompletion", new_callable=AsyncMock
    ) as mock_acompletion:
        # 1. Non-streamed call
        mock_acompletion.return_value = mock_non_stream
        res_non_stream = await provider.chat(
            messages=[{"role": "user", "content": "test"}]
        )

        # 2. Streamed call
        mock_acompletion.return_value = fake_stream()
        tokens_received = []

        async def on_token(token: str):
            tokens_received.append(token)

        res_stream = await provider.chat(
            messages=[{"role": "user", "content": "test"}],
            on_token=on_token,
        )

        # Assert Parity
        assert res_stream.content == res_non_stream.content
        assert "".join(tokens_received) == res_non_stream.content
        assert res_stream.finish_reason == res_non_stream.finish_reason
        assert res_stream.has_tool_calls == res_non_stream.has_tool_calls


@pytest.mark.asyncio
async def test_streamed_tool_calls_reconstruction_parity():
    provider = LiteLLMProvider(api_key="mock-key", default_model="gpt-4o")

    # Stream yielding delta tool calls across 3 chunks
    async def fake_tool_stream():
        # Chunk 1: tool call init with name
        c1 = MagicMock()
        tc1 = MagicMock()
        tc1.index = 0
        tc1.id = "call_abc123"
        tc1.function.name = "execute_sql"
        tc1.function.arguments = '{"query": "'
        c1.choices = [
            MagicMock(
                delta=MagicMock(content=None, tool_calls=[tc1], reasoning_content=None),
                finish_reason=None,
            )
        ]
        yield c1

        # Chunk 2: tool call args continuation
        c2 = MagicMock()
        tc2 = MagicMock()
        tc2.index = 0
        tc2.id = None
        tc2.function.name = None
        tc2.function.arguments = 'SELECT * FROM users;"}'
        c2.choices = [
            MagicMock(
                delta=MagicMock(content=None, tool_calls=[tc2], reasoning_content=None),
                finish_reason=None,
            )
        ]
        yield c2

        # Chunk 3: finish reason tool_calls
        c3 = MagicMock()
        c3.choices = [
            MagicMock(
                delta=MagicMock(content=None, tool_calls=None, reasoning_content=None),
                finish_reason="tool_calls",
            )
        ]
        yield c3

    with patch(
        "amberclaw.providers.litellm_provider.acompletion", new_callable=AsyncMock
    ) as mock_acompletion:
        mock_acompletion.return_value = fake_tool_stream()

        res = await provider.chat(
            messages=[{"role": "user", "content": "Run query"}],
            tools=[{"type": "function", "function": {"name": "execute_sql"}}],
            on_token=AsyncMock(),
        )

        assert res.has_tool_calls is True
        assert len(res.tool_calls) == 1
        assert res.tool_calls[0].name == "execute_sql"
        assert res.tool_calls[0].arguments == {"query": "SELECT * FROM users;"}
        assert res.finish_reason == "tool_calls"
