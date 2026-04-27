"""LiteLLM provider implementation for multi-provider support."""

import hashlib
import os
import secrets
import string
from typing import Any, Awaitable, Callable

import json_repair
import time
import litellm
from litellm import acompletion, completion_cost
from loguru import logger

from amberclaw.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from amberclaw.utils.cost_tracker import log_usage
from amberclaw.providers.registry import find_by_model, find_gateway

# Standard chat-completion message keys.
_ALLOWED_MSG_KEYS = frozenset(
    {"role", "content", "tool_calls", "tool_call_id", "name", "reasoning_content"}
)
_CAPABILITY_CACHE: dict[str, dict[str, Any]] = {}
_ANTHROPIC_EXTRA_KEYS = frozenset({"thinking_blocks"})
_ALNUM = string.ascii_letters + string.digits


def _short_tool_id() -> str:
    """Generate a 9-char alphanumeric ID compatible with all providers (incl. Mistral)."""
    return "".join(secrets.choice(_ALNUM) for _ in range(9))


class LiteLLMProvider(LLMProvider):
    """
    LLM provider using LiteLLM for multi-provider support.

    Supports OpenRouter, Anthropic, OpenAI, Gemini, MiniMax, and many other providers through
    a unified interface.  Provider-specific logic is driven by the registry
    (see providers/registry.py) — no if-elif chains needed here.
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "anthropic/claude-4-opus",
        extra_headers: dict[str, str] | None = None,
        provider_name: str | None = None,
        fallback_models: list[str] | None = None,
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self.fallback_models = fallback_models or []
        self.extra_headers = extra_headers or {}

        # Detect gateway / local deployment.
        # provider_name (from config key) is the primary signal;
        # api_key / api_base are fallback for auto-detection.
        self._gateway = find_gateway(provider_name, api_key, api_base)

        # Configure environment variables
        if api_key:
            self._setup_env(api_key, api_base, default_model)

        if api_base:
            litellm.api_base = api_base

        # Disable LiteLLM logging noise
        litellm.suppress_debug_info = True
        # Drop unsupported parameters for providers (e.g., gpt-5 rejects some params)
        litellm.drop_params = True

    def _setup_env(self, api_key: str, api_base: str | None, model: str) -> None:
        """Set environment variables based on detected provider."""
        spec = self._gateway or find_by_model(model)
        if not spec:
            return
        if not spec.env_key:
            # OAuth/provider-only specs (for example: openai_codex)
            return

        # Gateway/local overrides existing env; standard provider doesn't
        if self._gateway:
            os.environ[spec.env_key] = api_key
        else:
            os.environ.setdefault(spec.env_key, api_key)

        # Resolve env_extras placeholders:
        #   {api_key}  → user's API key
        #   {api_base} → user's api_base, falling back to spec.default_api_base
        effective_base = api_base or spec.default_api_base
        for env_name, env_val in spec.env_extras:
            resolved = env_val.replace("{api_key}", api_key)
            resolved = resolved.replace("{api_base}", effective_base)
            os.environ.setdefault(env_name, resolved)

    def _resolve_model(self, model: str) -> str:
        """Resolve model name by applying provider/gateway prefixes."""
        if self._gateway:
            # Gateway mode: apply gateway prefix, skip provider-specific prefixes
            prefix = self._gateway.litellm_prefix
            if self._gateway.strip_model_prefix:
                model = model.split("/")[-1]
            if prefix and not model.startswith(f"{prefix}/"):
                model = f"{prefix}/{model}"
            return model

        # Standard mode: auto-prefix for known providers
        spec = find_by_model(model)
        if spec and spec.litellm_prefix:
            model = self._canonicalize_explicit_prefix(model, spec.name, spec.litellm_prefix)
            if not any(model.startswith(s) for s in spec.skip_prefixes):
                model = f"{spec.litellm_prefix}/{model}"

        return model

    @staticmethod
    def _canonicalize_explicit_prefix(model: str, spec_name: str, canonical_prefix: str) -> str:
        """Normalize explicit provider prefixes like `github-copilot/...`."""
        if "/" not in model:
            return model
        prefix, remainder = model.split("/", 1)
        if prefix.lower().replace("-", "_") != spec_name:
            return model
        return f"{canonical_prefix}/{remainder}"

    def _supports_cache_control(self, model: str) -> bool:
        """Return True when the provider supports cache_control on content blocks."""
        caps = self.get_capabilities(model)
        return caps.get("prompt_caching", False)

    def _apply_cache_control(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]] | None]:
        """Return copies of messages and tools with cache_control injected."""
        new_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                content = msg["content"]
                if isinstance(content, str):
                    new_content = [
                        {"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}
                    ]
                else:
                    new_content = list(content)
                    new_content[-1] = {**new_content[-1], "cache_control": {"type": "ephemeral"}}
                new_messages.append({**msg, "content": new_content})
            else:
                new_messages.append(msg)

        new_tools = tools
        if tools:
            new_tools = list(tools)
            new_tools[-1] = {**new_tools[-1], "cache_control": {"type": "ephemeral"}}

        return new_messages, new_tools

    def get_capabilities(self, model: str) -> dict[str, Any]:
        """Detect model capabilities (vision, tools, JSON, etc.) via LiteLLM."""
        if model in _CAPABILITY_CACHE:
            return _CAPABILITY_CACHE[model]

        try:
            info = litellm.get_model_info(model)
            caps = {
                "vision": info.get("supports_vision", False),
                "tools": info.get("supports_function_calling", False),
                "json": info.get("supports_response_schema", False),
                "context_size": info.get("max_input_tokens", 4096),
                "prompt_caching": info.get("supports_prompt_caching", False),
            }
        except Exception:
            # Fallback for unknown models
            caps = {
                "vision": "vision" in model.lower(),
                "tools": True,
                "json": True,
                "context_size": 4096,
                "prompt_caching": False,
            }

        _CAPABILITY_CACHE[model] = caps
        return caps

    def _apply_model_overrides(self, model: str, kwargs: dict[str, Any]) -> None:
        """Apply model-specific parameter overrides from the registry."""
        model_lower = model.lower()
        spec = find_by_model(model)
        if spec:
            for pattern, overrides in spec.model_overrides:
                if pattern in model_lower:
                    kwargs.update(overrides)
                    return

    @staticmethod
    def _extra_msg_keys(original_model: str, resolved_model: str) -> frozenset[str]:
        """Return provider-specific extra keys to preserve in request messages."""
        spec = find_by_model(original_model) or find_by_model(resolved_model)
        if (
            (spec and spec.name == "anthropic")
            or "claude" in original_model.lower()
            or resolved_model.startswith("anthropic/")
        ):
            return _ANTHROPIC_EXTRA_KEYS
        return frozenset()

    @staticmethod
    def _normalize_tool_call_id(tool_call_id: Any) -> Any:
        """Normalize tool_call_id to a provider-safe 9-char alphanumeric form."""
        if not isinstance(tool_call_id, str):
            return tool_call_id
        if len(tool_call_id) == 9 and tool_call_id.isalnum():
            return tool_call_id
        return hashlib.sha256(tool_call_id.encode()).hexdigest()[:9]

    @staticmethod
    def _sanitize_messages(
        messages: list[dict[str, Any]], extra_keys: frozenset[str] = frozenset()
    ) -> list[dict[str, Any]]:
        """Strip non-standard keys and ensure assistant messages have a content key."""
        allowed = _ALLOWED_MSG_KEYS | extra_keys
        sanitized = LLMProvider._sanitize_request_messages(messages, allowed)
        id_map: dict[str, str] = {}

        def map_id(value: Any) -> Any:
            if not isinstance(value, str):
                return value
            return id_map.setdefault(value, LiteLLMProvider._normalize_tool_call_id(value))

        for clean in sanitized:
            # Keep assistant tool_calls[].id and tool tool_call_id in sync after
            # shortening, otherwise strict providers reject the broken linkage.
            if isinstance(clean.get("tool_calls"), list):
                normalized_tool_calls = []
                for tc in clean["tool_calls"]:
                    if not isinstance(tc, dict):
                        normalized_tool_calls.append(tc)
                        continue
                    tc_clean = dict(tc)
                    tc_clean["id"] = map_id(tc_clean.get("id"))
                    normalized_tool_calls.append(tc_clean)
                clean["tool_calls"] = normalized_tool_calls

            if "tool_call_id" in clean and clean["tool_call_id"]:
                clean["tool_call_id"] = map_id(clean["tool_call_id"])
        return sanitized

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        on_token: Callable[[str], Awaitable[None]] | None = None,
    ) -> LLMResponse:
        """Send a chat completion request via LiteLLM (supports streaming)."""
        original_model = model or self.default_model
        model = self._resolve_model(original_model)
        extra_msg_keys = self._extra_msg_keys(original_model, model)

        if self._supports_cache_control(original_model):
            messages, tools = self._apply_cache_control(messages, tools)

        max_tokens = max(1, max_tokens)

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": self._sanitize_messages(
                self._sanitize_empty_content(messages), extra_keys=extra_msg_keys
            ),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        self._apply_model_overrides(model, kwargs)

        # AC-087: OpenAI Caching Hints
        if "openai/" in model or model.startswith("gpt-"):
             kwargs["prompt_cache_key"] = "amberclaw-default-cache"
             kwargs["prompt_cache_retention"] = "24h"

        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.extra_headers:
            kwargs["extra_headers"] = self.extra_headers
        if reasoning_effort:
            # Anthropic handles thinking differently
            if "claude" in model.lower() or model.startswith("anthropic/"):
                kwargs["thinking"] = {"type": "enabled", "budget_tokens": max(1024, max_tokens // 2)}
                # Drop max_tokens if thinking is enabled, or adjust it
            else:
                kwargs["reasoning_effort"] = reasoning_effort
            kwargs["drop_params"] = True

        if tools:
            caps = self.get_capabilities(model)
            if not caps["tools"]:
                logger.warning("Model {} might not support tool calls natively.", model)

            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

            # AC-088: Enforce structured outputs if supported
            if caps["json"]:
                kwargs["response_format"] = {"type": "json_object"}
            # Disable streaming when tools are present to ensure reliable tool_calls parsing,
            # unless on_token is explicitly provided AND we want to risk it (not recommended for tools).
            # For now, we prefer atomic tool calls.
            # However, some models support streaming tool calls.
            # We'll stick to non-streaming for tools for now.
        elif on_token:
            kwargs["stream"] = True

        start_time = time.perf_counter()
        ttft_time = 0.0

        # AC-084: Fallback Routing
        models_to_try = [original_model] + getattr(self, "fallback_models", [])
        last_error = None

        for current_model_id in models_to_try:
            model = self._resolve_model(current_model_id)
            kwargs["model"] = model
            # Re-apply overrides for the fallback model
            self._apply_model_overrides(model, kwargs)
            
            try:
                response = await acompletion(**kwargs)

                if kwargs.get("stream"):
                    full_content = []
                    async for chunk in response:  # type: ignore
                        content = chunk.choices[0].delta.content or ""
                        if content:
                            if not full_content:
                                ttft_time = time.perf_counter() - start_time
                            full_content.append(content)
                            if on_token and callable(on_token):
                                await on_token(content)
                    
                    latency = (time.perf_counter() - start_time) * 1000
                    res = LLMResponse(
                        content="".join(full_content),
                        finish_reason="stop",
                        latency_ms=latency,
                        ttft_ms=ttft_time * 1000 if ttft_time else 0,
                    )
                    log_usage(model, res)
                    return res

                latency = (time.perf_counter() - start_time) * 1000
                res = self._parse_response(response)
                res.latency_ms = latency
                log_usage(model, res)
                return res

            except Exception as e:
                last_error = e
                logger.warning("Provider {} failed for model {}: {}. Trying fallback...", 
                               self.get_provider_name(current_model_id), current_model_id, str(e))
                # Small sleep before fallback if needed, but requirements say "within 5 seconds"
                continue

        return LLMResponse(
            content=f"All models failed. Last error: {str(last_error)}",
            finish_reason="error",
        )

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse LiteLLM response into our standard format."""
        choice = response.choices[0]
        message = choice.message
        content = message.content
        finish_reason = choice.finish_reason

        # Some providers (e.g. GitHub Copilot) split content and tool_calls
        # across multiple choices. Merge them so tool_calls are not lost.
        raw_tool_calls = []
        for ch in response.choices:
            msg = ch.message
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                raw_tool_calls.extend(msg.tool_calls)
                if ch.finish_reason in ("tool_calls", "stop"):
                    finish_reason = ch.finish_reason
            if not content and msg.content:
                content = msg.content

        if len(response.choices) > 1:
            logger.debug(
                "LiteLLM response has {} choices, merged {} tool_calls",
                len(response.choices),
                len(raw_tool_calls),
            )

        tool_calls = []
        for tc in raw_tool_calls:
            # Parse arguments from JSON string if needed
            args = tc.function.arguments
            if isinstance(args, str):
                args = json_repair.loads(args)

            tool_calls.append(
                ToolCallRequest(
                    id=_short_tool_id(),
                    name=tc.function.name,
                    arguments=args if isinstance(args, dict) else {"raw": str(args)},
                )
            )

        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        reasoning_content = getattr(message, "reasoning_content", None) or None
        thinking_blocks = getattr(message, "thinking_blocks", None) or None

        cost = 0.0
        try:
            cost = completion_cost(completion_response=response)
        except Exception:
            pass

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason or "stop",
            usage=usage,
            cost=cost,
            reasoning_content=reasoning_content,
            thinking_blocks=thinking_blocks,
        )

    def get_default_model(self) -> str:
        """Get the default model."""
        return self.default_model

    def to_langchain_chat(self, model: str | None = None, **kwargs: Any) -> Any:
        """Convert this provider to a LangChain ChatLiteLLM model."""
        from langchain_community.chat_models import ChatLiteLLM
        from pydantic import SecretStr

        target_model = model or self.default_model
        resolved = self._resolve_model(target_model)

        chat_kwargs = {
            "model": resolved,
            "api_key": SecretStr(self.api_key) if self.api_key else None,
            "api_base": self.api_base,
            "extra_headers": self.extra_headers,
            **kwargs,
        }
        return ChatLiteLLM(**chat_kwargs)
