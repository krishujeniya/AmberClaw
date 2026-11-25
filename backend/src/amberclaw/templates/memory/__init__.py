"""Memory template definitions and default memory markdown loading."""

from pathlib import Path

MEMORY_TEMPLATE_FILE: Path = Path(__file__).parent / "MEMORY.md"


def get_default_memory_template() -> str:
    """Return standard workspace MEMORY.md template content."""
    if MEMORY_TEMPLATE_FILE.exists():
        return MEMORY_TEMPLATE_FILE.read_text(encoding="utf-8")
    return "# Memory\n\nLong-term knowledge and conversational history.\n"


__all__ = [
    "MEMORY_TEMPLATE_FILE",
    "get_default_memory_template",
]
