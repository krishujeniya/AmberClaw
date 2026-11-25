"""Memory poisoning and prompt injection defense sanitizer.

Protects agent memory and RAG ingestion from prompt injections, role-spoofing
markers, invisible unicode manipulation, and jailbreak signatures.
"""

from __future__ import annotations

import re

# Invisible, formatting, and bidirectional override characters
_INVISIBLE_CHARS_RE = re.compile(
    r"[\u200B-\u200D\uFEFF\u200E\u200F\u202A-\u202E\u2060-\u206F]"
)

# Known LLM role delimiters and prompt template injection tags
_ROLE_DELIMITER_PATTERNS = [
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"<\|system\|>",
    r"<\|user\|>",
    r"<\|assistant\|>",
    r"<<SYS>>",
    r"<</SYS>>",
    r"\[INST\]",
    r"\[/INST\]",
    r"\b(?:system|human|assistant|developer)\s*:\s*\n",
    r"###\s*(?:System|Human|Assistant|Instruction)\s*:",
]
_DELIMITER_RE = re.compile("|".join(_ROLE_DELIMITER_PATTERNS), flags=re.IGNORECASE)

# Explicit instruction override and jailbreak patterns
_INJECTION_DIRECTIVES = [
    r"\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions\b",
    r"\bdisregard\s+(?:all\s+)?(?:previous|prior|above)\s+instructions\b",
    r"\boverride\s+(?:the\s+)?system\s+prompt\b",
    r"\byou\s+are\s+now\s+in\s+(?:developer|dan|god)\s+mode\b",
    r"\bbypass\s+all\s+safety\s+(?:filters|protocols)\b",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_DIRECTIVES), flags=re.IGNORECASE)


class MemorySanitizer:
    """Sanitizes text ingested into memory to prevent memory poisoning."""

    @classmethod
    def sanitize_text(cls, text: str) -> tuple[str, bool]:
        """Sanitize text against memory poisoning and prompt injection.

        Returns:
            tuple[str, bool]: (sanitized_text, was_poisoning_detected)
        """
        if not text:
            return text, False

        detected = False
        cleaned = text

        # 1. Strip invisible / zero-width characters
        if _INVISIBLE_CHARS_RE.search(cleaned):
            detected = True
            cleaned = _INVISIBLE_CHARS_RE.sub("", cleaned)

        # 2. Neutralize chat template role delimiters
        if _DELIMITER_RE.search(cleaned):
            detected = True
            cleaned = _DELIMITER_RE.sub("[SANITIZED_DELIMITER]", cleaned)

        # 3. Neutralize jailbreak / override directives
        if _INJECTION_RE.search(cleaned):
            detected = True
            cleaned = _INJECTION_RE.sub("[SANITIZED_DIRECTIVE]", cleaned)

        return cleaned, detected
