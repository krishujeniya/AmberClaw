"""Pre-inference and post-inference personally identifiable information (PII) scanner and redaction engine."""

import re
from typing import ClassVar

from loguru import logger
from pydantic import BaseModel, Field


class PIIMatch(BaseModel):
    """Detected sensitive entity with positional offset."""

    entity_type: str = Field(
        ..., description="Classification category (e.g. email, phone, ssn)"
    )
    value: str = Field(..., description="Original raw detected string")
    start: int = Field(..., ge=0)
    end: int = Field(..., ge=0)


class PIIScanResult(BaseModel):
    """Aggregate result of a PII inspection pass."""

    has_pii: bool = False
    matches: list[PIIMatch] = Field(default_factory=list)
    sanitized_text: str


class InferencePIIScanner:
    """Detects, audits, and redacts sensitive credentials and PII patterns prior to outbound LLM requests."""

    PATTERNS: ClassVar[dict[str, re.Pattern[str]]] = {
        "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"),
        "phone": re.compile(
            r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
        ),
        "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
        "api_key": re.compile(
            r"\b(?:sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{36}|AIza[0-9A-Za-z-_]{35})\b"
        ),
    }

    def __init__(self, mask_template: str = "[REDACTED_{entity}]") -> None:
        self.mask_template = mask_template

    def scan(self, text: str) -> PIIScanResult:
        """Scan input text for sensitive patterns and return detected entities and redacted text."""
        if not text:
            return PIIScanResult(has_pii=False, matches=[], sanitized_text="")

        matches: list[PIIMatch] = []
        sanitized = text

        for entity, pattern in self.PATTERNS.items():
            for m in pattern.finditer(text):
                matches.append(
                    PIIMatch(
                        entity_type=entity,
                        value=m.group(),
                        start=m.start(),
                        end=m.end(),
                    )
                )

        if not matches:
            return PIIScanResult(has_pii=False, matches=[], sanitized_text=text)

        # Sort matches by start position descending to replace without offset corruption
        sorted_matches = sorted(matches, key=lambda x: x.start, reverse=True)
        for m in sorted_matches:
            replacement = self.mask_template.format(entity=m.entity_type.upper())
            sanitized = sanitized[: m.start] + replacement + sanitized[m.end :]

        logger.info(
            "PII scanner detected {} sensitive occurrences in text", len(matches)
        )
        return PIIScanResult(
            has_pii=True,
            matches=matches,
            sanitized_text=sanitized,
        )

    def redact(self, text: str) -> str:
        """Convenience method returning solely the sanitized string."""
        return self.scan(text).sanitized_text
