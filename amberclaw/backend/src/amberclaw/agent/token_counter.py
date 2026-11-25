"""Token counter utilities for AmberClaw agent runtime."""

from typing import Any

try:
    import tiktoken

    _TIKTOKEN_AVAILABLE = True
except ImportError:
    tiktoken = None  # type: ignore[assignment]
    _TIKTOKEN_AVAILABLE = False


def count_tokens(messages: list[dict[str, Any]], model: str = "gpt-4o") -> int:
    """Accurately count tokens using tiktoken BPE tokenizer with fallback."""
    if _TIKTOKEN_AVAILABLE and tiktoken is not None:
        try:
            encoding = tiktoken.encoding_for_model(model)
        except Exception:
            encoding = tiktoken.get_encoding("cl100k_base")
        total = 0
        for m in messages:
            content = str(m.get("content", ""))
            total += len(encoding.encode(content)) + 4
        return total
    return sum(len(str(m.get("content", ""))) for m in messages) // 4
