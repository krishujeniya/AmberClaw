"""Context window compression and conversation history summarizer."""

from typing import Any

from pydantic import BaseModel, Field

_MAX_TRUNCATE_LEN = 80


class CompressionResult(BaseModel):
    """Result of context compression."""

    compressed_messages: list[dict[str, Any]]
    tokens_before: int
    tokens_after: int
    compression_ratio: float = Field(default=1.0, description="tokens_after / tokens_before")
    summarized_turn_count: int = Field(default=0, description="Number of historical turns condensed")


class ContextCompressor:
    """Condenses older conversation turns to fit within context limits."""

    def __init__(self, max_tokens: int = 4000, keep_recent: int = 4) -> None:
        self.max_tokens = max_tokens
        self.keep_recent = keep_recent

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count based on character heuristic (approx 4 chars per token)."""
        return max(1, len(text) // 4)

    def count_message_tokens(self, messages: list[dict[str, Any]]) -> int:
        """Count total tokens across a list of message dicts."""
        total = 0
        for m in messages:
            content = str(m.get("content") or "")
            total += self.estimate_tokens(content) + 4  # overhead for role
        return total

    def compress(self, messages: list[dict[str, Any]]) -> CompressionResult:
        """Condense historical turns if message list exceeds max token limits."""
        tokens_before = self.count_message_tokens(messages)

        if tokens_before <= self.max_tokens or len(messages) <= (self.keep_recent + 1):
            return CompressionResult(
                compressed_messages=messages,
                tokens_before=tokens_before,
                tokens_after=tokens_before,
                compression_ratio=1.0,
                summarized_turn_count=0,
            )

        # Separate system prompt, older history, and recent turns
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        to_summarize = non_system[:-self.keep_recent]
        recent = non_system[-self.keep_recent:]

        # Create concise historical summary card
        summary_lines = []
        for m in to_summarize:
            role = m.get("role", "unknown")
            content = str(m.get("content", ""))
            truncated = content[:_MAX_TRUNCATE_LEN] + ("..." if len(content) > _MAX_TRUNCATE_LEN else "")
            summary_lines.append(f"- [{role}]: {truncated}")

        summary_content = (
            "[Context Summary of Previous Turns]\n"
            + "\n".join(summary_lines)
        )

        compressed: list[dict[str, Any]] = []
        if system_msgs:
            compressed.extend(system_msgs)
        compressed.append({"role": "system", "content": summary_content})
        compressed.extend(recent)

        tokens_after = self.count_message_tokens(compressed)
        ratio = round(tokens_after / max(1, tokens_before), 2)

        return CompressionResult(
            compressed_messages=compressed,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            compression_ratio=ratio,
            summarized_turn_count=len(to_summarize),
        )
