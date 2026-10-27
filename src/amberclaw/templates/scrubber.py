"""Template variable secret and PII scrubber."""

import re
from typing import Any

from amberclaw.security.secret_scanner import SecretScanner


class TemplateScrubber:
    """Scrubs secrets and PII from template variables and context dictionaries."""

    @staticmethod
    def scrub_context(context: dict[str, Any]) -> dict[str, Any]:
        """Scrub secret strings in context values."""
        scrubbed = {}
        for key, val in context.items():
            if isinstance(val, str):
                scrubbed[key] = SecretScanner.redact_text(val)
            else:
                scrubbed[key] = val
        return scrubbed

    @staticmethod
    def scrub_rendered_template(content: str) -> str:
        """Scrub secret strings from rendered template markdown content."""
        return SecretScanner.redact_text(content)
