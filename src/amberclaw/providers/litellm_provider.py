"""LiteLLM provider implementation for multi-provider support."""

import hashlib
import os
import secrets
import string
import time
from collections.abc import Awaitable, Callable, Generator
from contextlib import contextmanager
from typing import Any

import json_repair
import litellm
from litellm import acompletion, completion_cost
from loguru import logger

from amberclaw.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from amberclaw.providers.registry import find_by_model, find_gateway
from amberclaw.utils.cost_tracker import log_usage

# Standard chat-completion message keys.
_ALLOWED_MSG_KEYS = frozenset(
    {"role", "content", "tool_calls", "tool_call_id", "name", "reasoning_content"},
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
        enable_prompt_caching: bool = True,
        enforce_strict_tools: bool = True,
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self.fallback_models = fallback_models or []
        self.extra_headers = extra_headers or {}
        self.enable_prompt_caching = enable_prompt_caching
        self.enforce_strict_tools = enforce_strict_tools

        # Detect gateway / local deployment.
        # provider_name (from config key) is the primary signal;
        # api_key / api_base are fallback for auto-detection.
        self._gateway = find_gateway(provider_name, api_key, api_base)

        # Configure environment variables
        if api_key and not api_key.startswith("vault://"):
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

    @contextmanager
    def _env_context(
        self, resolved_key: str | None, model: str
    ) -> Generator[None, None, None]:
        """Temporarily set environment variables for the duration of an LLM call."""
        if not resolved_key:
            yield
            return

        spec = self._gateway or find_by_model(model)
        if not spec or not spec.env_key:
            yield
            return

        old_env = {}
        old_env[spec.env_key] = os.environ.get(spec.env_key)
        if self._gateway:
            os.environ[spec.env_key] = resolved_key
        else:
            os.environ.setdefault(spec.env_key, resolved_key)

        effective_base = self.api_base or spec.default_api_base
        for env_name, env_val in spec.env_extras:
            resolved = env_val.replace("{api_key}", resolved_key)
            resolved = resolved.replace("{api_base}", effective_base)
            old_env[env_name] = os.environ.get(env_name)
            os.environ.setdefault(env_name, resolved)

        try:
            yield
        finally:
            for k, val in old_env.items():
                if val is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = val

    def _resolve_model(self, model: str) -> str:
        """Resolve model name by applying provider/gateway prefixes."""
        if self._gateway:
            # Gateway mode: apply gateway prefix, skip provider-specific prefixes
            prefix = self._gateway.litellm_prefix
            if self._gateway.strip_model_prefix:
                model = model.rsplit("/", maxsplit=1)[-1]
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
        if not getattr(self, "enable_prompt_caching", True):
            return False
        caps = self.get_capabilities(model)
        return caps.get("prompt_caching", False)

    def _apply_cache_control(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]] | None]:
        """Return copies of messages and tools with cache_control injected."""
        if not getattr(self, "enable_prompt_caching", True):
            return messages, tools

        new_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                content = msg["content"]
                if isinstance(content, str):
                    new_content = [
                        {"type": "text", "text": content, "cache_control": {"type": "ephemeral"}},
                    ]
                else:
                    new_content = list(content)
                    if new_content:
                        new_content[-1] = {**new_content[-1], "cache_control": {"type": "ephemeral"}}
                new_messages.append({**msg, "content": new_content})
            else:
                new_messages.append(msg)

        new_tools = tools
        if tools:
            new_tools = list(tools)
            new_tools[-1] = {**new_tools[-1], "cache_control": {"type": "ephemeral"}}

        msg_indices = [
            i for i, msg in enumerate(new_messages)
            if msg.get("role") in ("user", "assistant")
        ]

        breakpoints_to_add = []
        if len(msg_indices) >= 4:
            mid_idx = msg_indices[len(msg_indices) // 2]
            breakpoints_to_add.append(mid_idx)
            end_idx = msg_indices[-2]
            if end_idx not in breakpoints_to_add:
                breakpoints_to_add.append(end_idx)
        elif len(msg_indices) >= 2:
            breakpoints_to_add.append(msg_indices[0])

        for idx in breakpoints_to_add:
            msg = new_messages[idx]
            content = msg.get("content")
            if isinstance(content, str):
                new_content = [
                    {"type": "text", "text": content, "cache_control": {"type": "ephemeral"}},
                ]
                new_messages[idx] = {**msg, "content": new_content}
            elif isinstance(content, list) and content:
                new_content = list(content)
                new_content[-1] = {**new_content[-1], "cache_control": {"type": "ephemeral"}}
                new_messages[idx] = {**msg, "content": new_content}

        return new_messages, new_tools

    def get_capabilities(self, model: str) -> dict[str, Any]:
        """Detect model capabilities (vision, tools, JSON, etc.) via LiteLLM."""
        if model in _CAPABILITY_CACHE:
            return _CAPABILITY_CACHE[model]

        lookup_model = model
        if "/" in model:
            lookup_model = model.split("/")[-1]

        try:
            info = litellm.get_model_info(lookup_model)
            caps = {
                "vision": info.get("supports_vision", False),
                "tools": info.get("supports_function_calling", True),
                "json": info.get("supports_response_schema", False),
                "context_size": info.get("max_input_tokens", 4096) or 4096,
                "prompt_caching": info.get("supports_prompt_caching", False),
                "reasoning": info.get("supports_reasoning", False) or any(
                    x in lookup_model.lower() for x in ["o1-", "o3-", "deepseek-r1", "reasoner"]
                ),
            }
        except Exception:
            # Fallback for unknown models
            model_lower = model.lower()
            caps = {
                "vision": any(x in model_lower for x in ["vision", "claude-3", "gpt-4o", "gemini-1.5", "gemini-2.0", "pixtral"]),
                "tools": True,
                "json": True,
                "context_size": 128000 if any(x in model_lower for x in ["gpt-4", "claude-3", "gemini"]) else 4096,
                "prompt_caching": any(x in model_lower for x in ["claude-3-5", "gpt-4o"]),
                "reasoning": any(x in model_lower for x in ["o1-", "o3-", "deepseek-r1", "reasoner"]),
            }

        # Override/augment for known high-capacity models
        model_lower = model.lower()
        if "claude-3-5" in model_lower:
            caps["context_size"] = 200000
            caps["vision"] = True
            caps["prompt_caching"] = True
        elif "gpt-4o" in model_lower:
            caps["context_size"] = 128000
            caps["vision"] = True
            caps["prompt_caching"] = True
        elif "gemini-1.5" in model_lower or "gemini-2.0" in model_lower:
            caps["context_size"] = 1000000
            caps["vision"] = True

        _CAPABILITY_CACHE[model] = caps
        return caps

    def _analyze_requirements(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]:
        """Analyze prompt structure and settings to detect needed capabilities."""
        requires_vision = False
        requires_reasoning = bool(reasoning_effort)

        # 1. Inspect messages for image objects/urls
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") in ("image_url", "image") or "image_url" in block or "image" in block:
                            requires_vision = True
                            break
            elif isinstance(content, dict):
                if content.get("type") in ("image_url", "image") or "image_url" in content or "image" in content:
                    requires_vision = True
            if requires_vision:
                break

        # 2. Check for reasoning hints in user/system prompts
        if not requires_reasoning:
            for msg in messages:
                if msg.get("role") in ("user", "system"):
                    content_str = str(msg.get("content") or "")
                    if any(kw in content_str.lower() for kw in ["reason deep", "deep thinking", "step-by-step reasoning"]):
                        requires_reasoning = True
                        break

        # 3. Estimate token consumption for context size
        estimated_tokens = 0
        try:
            estimated_tokens = litellm.token_counter(model="gpt-3.5-turbo", messages=messages)
            estimated_tokens += len(str(tools or "")) // 4
        except Exception:
            estimated_tokens += len(str(tools or "")) // 4
            for msg in messages:
                content = msg.get("content")
                if isinstance(content, str):
                    estimated_tokens += len(content) // 4
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            estimated_tokens += len(str(block.get("text", ""))) // 4
                        else:
                            estimated_tokens += len(str(block)) // 4

        # Add buffer for completion generation
        required_context = int(estimated_tokens * 1.15) + 1024

        return {
            "vision": requires_vision,
            "reasoning": requires_reasoning,
            "context_size": required_context,
        }

    def _select_optimal_model(self, original_model: str, requirements: dict[str, Any]) -> str:
        """Find the first candidate model satisfying all requirements."""
        candidates = [original_model] + self.fallback_models
        for candidate in candidates:
            caps = self.get_capabilities(candidate)
            if requirements["vision"] and not caps.get("vision", False):
                continue
            if requirements["reasoning"] and not caps.get("reasoning", False):
                continue
            if requirements["context_size"] > caps.get("context_size", 4096):
                continue
            
            if candidate != original_model:
                logger.info(
                    "🔄 Dynamic Routing: switched from '{}' to '{}' based on requirements {}",
                    original_model,
                    candidate,
                    requirements,
                )
            return candidate

        logger.warning(
            "⚠️ No fallback models satisfied requirements {}. Defaulting to '{}'",
            requirements,
            original_model,
        )
        return original_model


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
        messages: list[dict[str, Any]], extra_keys: frozenset[str] = frozenset(),
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

            if clean.get("tool_call_id"):
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
        response_format: dict[str, Any] | None = None,
        on_token: Callable[[str], Awaitable[None]] | None = None,
    ) -> LLMResponse:
        """Send a chat completion request via LiteLLM (supports streaming)."""
        original_model = model or self.default_model
        requirements = self._analyze_requirements(messages, tools, reasoning_effort)
        optimal_model = self._select_optimal_model(original_model, requirements)

        if self._supports_cache_control(optimal_model):
            messages, tools = self._apply_cache_control(messages, tools)

        max_tokens = max(1, max_tokens)

        # Pre-sanitize messages content
        sanitized_messages = self._sanitize_empty_content(messages)

        # Detect if JSON response is expected
        expects_json = False
        if response_format is not None:
            expects_json = True
        else:
            json_keywords = ["json format", "json object", "respond in json", "output json", "valid json"]
            for msg in messages:
                content = msg.get("content", "")
                if isinstance(content, str):
                    if any(kw in content.lower() for kw in json_keywords):
                        expects_json = True
                        break
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            txt = block.get("text", "")
                            if any(kw in txt.lower() for kw in json_keywords):
                                expects_json = True
                                break

        kwargs: dict[str, Any] = {
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        from amberclaw.security.vault import resolved_secrets_context

        with resolved_secrets_context(self.api_key) as resolved_key:
            if resolved_key:
                kwargs["api_key"] = resolved_key
            if self.api_base:
                kwargs["api_base"] = self.api_base

            # Build extra headers
            headers = dict(self.extra_headers or {})
            if getattr(self, "enable_prompt_caching", True):
                if self._gateway and self._gateway.name == "openrouter":
                    headers["X-OpenRouter-Cache"] = "true"
            if headers:
                kwargs["extra_headers"] = headers

            start_time = time.perf_counter()
            ttft_time = 0.0

            # AC-084: Fallback Routing
            models_to_try = [optimal_model] + [m for m in getattr(self, "fallback_models", []) if m != optimal_model]
            last_error = None

            for current_model_id in models_to_try:
                model = self._resolve_model(current_model_id)
                kwargs["model"] = model

                # Clean messages specifically for this model
                extra_msg_keys = self._extra_msg_keys(current_model_id, model)
                kwargs["messages"] = self._sanitize_messages(
                    sanitized_messages, extra_keys=extra_msg_keys,
                )

                # Re-apply overrides for the fallback model
                self._apply_model_overrides(model, kwargs)

                # AC-087: OpenAI Caching Hints
                if "openai/" in model or model.startswith("gpt-"):
                     kwargs["prompt_cache_key"] = "amberclaw-default-cache"
                     kwargs["prompt_cache_retention"] = "24h"
                else:
                     kwargs.pop("prompt_cache_key", None)
                     kwargs.pop("prompt_cache_retention", None)

                if reasoning_effort:
                    # Anthropic handles thinking differently
                    if "claude" in model.lower() or model.startswith("anthropic/"):
                        kwargs["thinking"] = {
                            "type": "enabled",
                            "budget_tokens": max(1024, max_tokens // 2),
                        }
                    else:
                        kwargs["reasoning_effort"] = reasoning_effort
                    kwargs["drop_params"] = True
                else:
                    kwargs.pop("thinking", None)
                    kwargs.pop("reasoning_effort", None)
                    kwargs.pop("drop_params", None)

                # Get model capabilities dynamically
                caps = self.get_capabilities(current_model_id)

                # Configure tools
                if tools:
                    if not caps["tools"]:
                        logger.warning(
                            "Model {} might not support tool calls natively.", model
                        )

                    final_tools = tools
                    if getattr(self, "enforce_strict_tools", True) and caps.get("json"):
                        final_tools = [self._make_tool_strict(t) for t in tools]

                    kwargs["tools"] = final_tools
                    kwargs["tool_choice"] = "auto"
                    kwargs.pop("response_format", None)
                else:
                    kwargs.pop("tools", None)
                    kwargs.pop("tool_choice", None)

                    # Configure response_format for JSON mode
                    if expects_json:
                        if response_format is not None:
                            kwargs["response_format"] = response_format
                        elif caps.get("json"):
                            kwargs["response_format"] = {"type": "json_object"}
                        else:
                            kwargs.pop("response_format", None)
                    else:
                        kwargs.pop("response_format", None)

                if on_token:
                    kwargs["stream"] = True
                else:
                    kwargs.pop("stream", None)

                with self._env_context(resolved_key, model):
                    try:
                        response = await acompletion(**kwargs)

                        if kwargs.get("stream"):
                            full_content = []
                            async for chunk in response:  # type: ignore
                                content = (
                                    chunk.choices[0].delta.content or ""
                                )
                                if content:
                                    if not full_content:
                                        ttft_time = (
                                            time.perf_counter() - start_time
                                        )
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
                        logger.warning(
                            "Provider {} failed for model {}: {}. Trying fallback...",
                            self.get_provider_name(current_model_id),
                            current_model_id,
                            str(e),
                        )
                        continue

            return LLMResponse(
                content=f"All models failed. Last error: {last_error!s}",
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
                ),
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

    def _make_tool_strict(self, tool_def: dict[str, Any]) -> dict[str, Any]:
        """Convert a tool definition to support strict schema enforcement."""
        if not isinstance(tool_def, dict) or "function" not in tool_def:
            return tool_def

        new_tool = dict(tool_def)
        new_func = dict(new_tool["function"])
        new_tool["function"] = new_func

        # Set strict to True on the function definition
        new_func["strict"] = True

        if "parameters" in new_func and isinstance(new_func["parameters"], dict):
            new_params = self._make_schema_strict(new_func["parameters"])
            new_func["parameters"] = new_params

        return new_tool

    def _make_schema_strict(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Recursively update a JSON schema to satisfy strictness requirements."""
        if not isinstance(schema, dict):
            return schema

        new_schema = dict(schema)

        # If type is object or properties are specified, add additionalProperties=False
        # and make all properties required
        if new_schema.get("type") == "object" or "properties" in new_schema:
            new_schema["additionalProperties"] = False
            properties = new_schema.get("properties", {})
            if properties and isinstance(properties, dict):
                # Ensure all property keys are present in required list
                req_list = list(new_schema.get("required", []))
                for prop_name in properties.keys():
                    if prop_name not in req_list:
                        req_list.append(prop_name)
                new_schema["required"] = req_list

                # Recursively apply strict schema to all properties
                new_props = {}
                for prop_name, prop_val in properties.items():
                    if isinstance(prop_val, dict):
                        new_props[prop_name] = self._make_schema_strict(prop_val)
                    else:
                        new_props[prop_name] = prop_val
                new_schema["properties"] = new_props
            else:
                # If it's an object type but has no properties, still set required if needed
                if "required" not in new_schema:
                    new_schema["required"] = []

        # Recursively update any sub-schemas (e.g. in items, anyOf, oneOf, allOf)
        for key in ["items", "anyOf", "oneOf", "allOf"]:
            if key in new_schema:
                val = new_schema[key]
                if isinstance(val, dict):
                    new_schema[key] = self._make_schema_strict(val)
                elif isinstance(val, list):
                    new_schema[key] = [self._make_schema_strict(item) for item in val]

        return new_schema

    def get_default_model(self) -> str:
        """Get the default model."""
        return self.default_model

    def to_langchain_chat(self, model: str | None = None, **kwargs: Any) -> Any:
        """Convert this provider to a LangChain ChatLiteLLM model."""
        from langchain_community.chat_models import ChatLiteLLM
        from pydantic import SecretStr
        from amberclaw.security.vault import vault

        target_model = model or self.default_model
        resolved = self._resolve_model(target_model)

        resolved_key = vault.resolve_secret(self.api_key)

        chat_kwargs = {
            "model": resolved,
            "api_key": SecretStr(resolved_key) if resolved_key else None,
            "api_base": self.api_base,
            "extra_headers": self.extra_headers,
            **kwargs,
        }
        return ChatLiteLLM(**chat_kwargs)

    def get_provider_name(self, model: str) -> str:
        """Get the provider name for a given model from the registry."""
        if self._gateway:
            return self._gateway.name
        spec = find_by_model(model)
        return spec.name if spec else "openai"

