"""PII Redactor for masking sensitive user data using Presidio or Regex fallback."""

import re

from loguru import logger

# Compiled regular expressions for common PII patterns (fallback)
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

    def __init__(self, placeholders: dict[str, str] | None = None):
        self.placeholders = placeholders or {
            "email": "[REDACTED_EMAIL]",
            "ip": "[REDACTED_IP]",
            "credit_card": "[REDACTED_CARD]",
            "phone": "[REDACTED_PHONE]",
            "person": "[REDACTED_PERSON]",
            "location": "[REDACTED_LOCATION]",
            "ssn": "[REDACTED_SSN]",
        }

        # Try to initialize Microsoft Presidio
        self.presidio_available = False
        self._analyzer = None
        self._anonymizer = None

        try:
            from presidio_analyzer import AnalyzerEngine  # noqa: PLC0415
            from presidio_anonymizer import AnonymizerEngine  # noqa: PLC0415

            self._analyzer = AnalyzerEngine()
            self._anonymizer = AnonymizerEngine()
            self.presidio_available = True
        except Exception as e:
            logger.debug("Presidio initialization failed: {}. Falling back to regex.", e)

    def redact(self, text: str) -> str:
        """Scan and redact PII patterns from text."""
        if not text:
            return text

        if self.presidio_available and self._analyzer and self._anonymizer:
            try:
                return self._redact_presidio(text)
            except Exception as e:
                logger.debug("Presidio redact failed: {}. Falling back to regex.", e)

        return self._redact_regex(text)

    def _redact_presidio(self, text: str) -> str:
        from presidio_anonymizer.entities import OperatorConfig  # noqa: PLC0415

        # Analyze text for PII
        results = self._analyzer.analyze(
            text=text,
            language="en",
            entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "IP_ADDRESS", "CREDIT_CARD", "US_SSN", "LOCATION"],
        )

        if not results:
            return text

        # Set custom operators for anonymization
        operators = {
            "PERSON": OperatorConfig("replace", {"new_value": self.placeholders.get("person", "[REDACTED_PERSON]")}),
            "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": self.placeholders.get("email", "[REDACTED_EMAIL]")}),
            "PHONE_NUMBER": OperatorConfig("replace", {"new_value": self.placeholders.get("phone", "[REDACTED_PHONE]")}),
            "IP_ADDRESS": OperatorConfig("replace", {"new_value": self.placeholders.get("ip", "[REDACTED_IP]")}),
            "CREDIT_CARD": OperatorConfig("replace", {"new_value": self.placeholders.get("credit_card", "[REDACTED_CARD]")}),
            "US_SSN": OperatorConfig("replace", {"new_value": self.placeholders.get("ssn", "[REDACTED_SSN]")}),
            "LOCATION": OperatorConfig("replace", {"new_value": self.placeholders.get("location", "[REDACTED_LOCATION]")}),
        }

        # Anonymize using the custom operators
        anonymized = self._anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators=operators,
        )
        return anonymized.text

    def _redact_regex(self, text: str) -> str:
        # Redact emails
        text = EMAIL_REGEX.sub(self.placeholders.get("email", "[REDACTED_EMAIL]"), text)
        # Redact IPs
        text = IP_REGEX.sub(self.placeholders.get("ip", "[REDACTED_IP]"), text)
        # Redact credit cards
        text = CREDIT_CARD_REGEX.sub(self.placeholders.get("credit_card", "[REDACTED_CARD]"), text)
        # Redact phones
        return PHONE_REGEX.sub(self.placeholders.get("phone", "[REDACTED_PHONE]"), text)
