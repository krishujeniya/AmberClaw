"""Pure Python PII Redactor for masking sensitive user data."""

import re
from typing import Dict

# Compiled regular expressions for common PII patterns
EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"
)
IP_REGEX = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
)
CREDIT_CARD_REGEX = re.compile(
    r"\b(?:\d[ -]*?){13,16}\b"
)
PHONE_REGEX = re.compile(
    r"\b(?:\+\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b"
)


class PIIRedactor:
    """PII Redactor for identifying and masking sensitive data in text."""

    def __init__(self, placeholders: Dict[str, str] | None = None):
        self.placeholders = placeholders or {
            "email": "[REDACTED_EMAIL]",
            "ip": "[REDACTED_IP]",
            "credit_card": "[REDACTED_CARD]",
            "phone": "[REDACTED_PHONE]",
        }

    def redact(self, text: str) -> str:
        """Scan and redact PII patterns from text."""
        if not text:
            return text

        # Redact emails
        text = EMAIL_REGEX.sub(self.placeholders.get("email", "[REDACTED_EMAIL]"), text)

        # Redact IPs
        text = IP_REGEX.sub(self.placeholders.get("ip", "[REDACTED_IP]"), text)

        # Redact credit cards
        text = CREDIT_CARD_REGEX.sub(self.placeholders.get("credit_card", "[REDACTED_CARD]"), text)

        # Redact phones
        text = PHONE_REGEX.sub(self.placeholders.get("phone", "[REDACTED_PHONE]"), text)

        return text
