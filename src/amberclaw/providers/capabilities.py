"""Provider capability contract for LLM models."""

from __future__ import annotations

import contextlib
from typing import Any

from pydantic import BaseModel, Field

with contextlib.suppress(ImportError):
    import litellm

# Cache detected capabilities to avoid repeated lookups
_CAPABILITY_CACHE: dict[str, ProviderCapability] = {}


class ProviderCapability(BaseModel):
    """Normalized capability contract for an LLM model/provider.

    Covers:
      - Tools / function calling
      - JSON mode / structured outputs
      - Multi-modal vision and audio
      - Streaming generation
      - Context window and max output tokens
      - Prompt caching
      - Reasoning / Chain-of-Thought
      - Pricing metadata (per token in USD)
    """

    model: str
    provider: str = ""
    tools: bool = True
    json_mode: bool = False
    vision: bool = False
    audio: bool = False
    streaming: bool = True
    context_window: int = 4096
    max_output_tokens: int = 4096
    prompt_caching: bool = False
    reasoning: bool = False
    input_cost_per_token: float = 0.0
    output_cost_per_token: float = 0.0
    pricing_source: str = "default"
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Aliases mapping for backward compatibility with dict-based access
    _ALIASES: dict[str, str] = {
        "context_size": "context_window",
        "json": "json_mode",
        "function_calling": "tools",
        "caching": "prompt_caching",
    }

    def __getitem__(self, item: str) -> Any:
        """Support dict-like indexing for backwards compatibility."""
        target = self._ALIASES.get(item, item)
        if hasattr(self, target):
            return getattr(self, target)
        if target in self.metadata:
            return self.metadata[target]
        raise KeyError(item)

    def get(self, item: str, default: Any = None) -> Any:
        """Support dict-like get for backwards compatibility."""
        try:
            return self[item]
        except KeyError:
            return default

    def __contains__(self, item: str) -> bool:
        target = self._ALIASES.get(item, item)
        return hasattr(self, target) or target in self.metadata

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict including legacy alias keys."""
        data = self.model_dump()
        data["context_size"] = self.context_window
        data["json"] = self.json_mode
        return data


def _fallback_capabilities(model_lower: str) -> dict[str, Any]:
    """Heuristic defaults when litellm.get_model_info is unavailable."""
    has_vision = any(
        x in model_lower
        for x in [
            "vision",
            "claude-3",
            "gpt-4o",
            "gemini-1.5",
            "gemini-2.0",
            "pixtral",
            "llava",
        ]
    )
    has_audio = any(
        x in model_lower for x in ["audio", "whisper", "gpt-4o-audio", "gemini-1.5"]
    )
    is_reasoning = any(
        x in model_lower for x in ["o1-", "o3-", "deepseek-r1", "reasoner"]
    )
    is_caching = any(x in model_lower for x in ["claude-3-5", "claude-3-7", "gpt-4o"])
    ctx = (
        128000
        if any(x in model_lower for x in ["gpt-4", "claude-3", "gemini"])
        else 4096
    )

    return {
        "vision": has_vision,
        "audio": has_audio,
        "tools": True,
        "json_mode": True,
        "streaming": True,
        "prompt_caching": is_caching,
        "reasoning": is_reasoning,
        "context_window": ctx,
        "max_output_tokens": 4096,
        "input_cost_per_token": 0.0,
        "output_cost_per_token": 0.0,
        "pricing_source": "default",
    }


def _apply_known_model_overrides(model_lower: str, values: dict[str, Any]) -> None:
    """Apply known architectural parameters and pricing for flagship models."""
    if "claude-3-5" in model_lower or "claude-3-7" in model_lower:
        values["context_window"] = 200000
        values["max_output_tokens"] = 8192
        values["vision"] = True
        values["prompt_caching"] = True
        if values.get("input_cost_per_token", 0.0) == 0.0:
            values["input_cost_per_token"] = 0.000003
            values["output_cost_per_token"] = 0.000015
            values["pricing_source"] = "catalog_standard"
    elif "gpt-4o-mini" in model_lower:
        values["context_window"] = 128000
        values["max_output_tokens"] = 16384
        values["vision"] = True
        values["prompt_caching"] = True
        if values.get("input_cost_per_token", 0.0) == 0.0:
            values["input_cost_per_token"] = 0.00000015
            values["output_cost_per_token"] = 0.0000006
            values["pricing_source"] = "catalog_standard"
    elif "gpt-4o" in model_lower:
        values["context_window"] = 128000
        values["max_output_tokens"] = 16384
        values["vision"] = True
        values["prompt_caching"] = True
        if values.get("input_cost_per_token", 0.0) == 0.0:
            values["input_cost_per_token"] = 0.0000025
            values["output_cost_per_token"] = 0.00001
            values["pricing_source"] = "catalog_standard"
    elif "gemini-1.5" in model_lower or "gemini-2.0" in model_lower:
        values["context_window"] = 1000000
        values["max_output_tokens"] = 8192
        values["vision"] = True
        values["audio"] = True
    elif "deepseek-r1" in model_lower:
        values["context_window"] = 64000
        values["max_output_tokens"] = 8192
        values["reasoning"] = True
        if values.get("input_cost_per_token", 0.0) == 0.0:
            values["input_cost_per_token"] = 0.00000055
            values["output_cost_per_token"] = 0.00000219
            values["pricing_source"] = "catalog_standard"


def detect_capabilities(
    model: str,
    provider: str = "",
    litellm_module: Any = None,
) -> ProviderCapability:
    """Detect model capabilities via LiteLLM or heuristic fallback."""
    if model in _CAPABILITY_CACHE and litellm_module is None:
        return _CAPABILITY_CACHE[model]

    lookup_model = model.rsplit("/", maxsplit=1)[-1] if "/" in model else model
    llm = litellm_module or litellm

    try:
        if not llm:
            raise RuntimeError("LiteLLM not available")
        info = llm.get_model_info(lookup_model)
        values = {
            "vision": bool(info.get("supports_vision", False)),
            "tools": bool(info.get("supports_function_calling", True)),
            "json_mode": bool(info.get("supports_response_schema", False)),
            "context_window": int(info.get("max_input_tokens", 4096) or 4096),
            "max_output_tokens": int(info.get("max_output_tokens", 4096) or 4096),
            "prompt_caching": bool(info.get("supports_prompt_caching", False)),
            "audio": bool(
                info.get("supports_audio", False)
                or info.get("supports_audio_input", False)
            ),
            "streaming": bool(info.get("supports_streaming", True)),
            "reasoning": bool(
                info.get("supports_reasoning", False)
                or any(
                    x in lookup_model.lower()
                    for x in ["o1-", "o3-", "deepseek-r1", "reasoner"]
                )
            ),
            "input_cost_per_token": float(info.get("input_cost_per_token", 0.0) or 0.0),
            "output_cost_per_token": float(
                info.get("output_cost_per_token", 0.0) or 0.0
            ),
            "pricing_source": "litellm_model_info",
        }
    except Exception:
        values = _fallback_capabilities(model.lower())

    _apply_known_model_overrides(model.lower(), values)

    cap = ProviderCapability(
        model=model,
        provider=provider,
        **values,
    )
    _CAPABILITY_CACHE[model] = cap
    return cap
