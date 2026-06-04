"""Unit tests for PII Redaction Engine."""

from unittest.mock import MagicMock, patch

from amberclaw.security.pii import PIIRedactor


def test_pii_redactor_regex_fallback():
    redactor = PIIRedactor()
    # Ensure Presidio is false for this fallback test
    redactor.presidio_available = False

    text = "My email is test@example.com, IP is 192.168.1.1, phone is 555-123-4567, card is 1234-5678-9012-3456."
    redacted = redactor.redact(text)

    assert "[REDACTED_EMAIL]" in redacted
    assert "[REDACTED_IP]" in redacted
    assert "[REDACTED_PHONE]" in redacted
    assert "[REDACTED_CARD]" in redacted
    assert "test@example.com" not in redacted
    assert "192.168.1.1" not in redacted


@patch("amberclaw.security.pii.PIIRedactor._redact_presidio")
def test_pii_redactor_presidio_called(mock_presidio_redact):
    redactor = PIIRedactor()
    redactor.presidio_available = True
    redactor._analyzer = MagicMock()
    redactor._anonymizer = MagicMock()

    mock_presidio_redact.return_value = "Mocked Redacted Output"

    res = redactor.redact("John Doe lives in New York")
    assert res == "Mocked Redacted Output"
    mock_presidio_redact.assert_called_once_with("John Doe lives in New York")


def test_pii_redactor_presidio_fallback_on_failure():
    redactor = PIIRedactor()
    redactor.presidio_available = True
    redactor._analyzer = MagicMock()
    redactor._anonymizer = MagicMock()

    # Force an exception to trigger the regex fallback
    redactor._analyzer.analyze.side_effect = Exception("Presidio failed")

    text = "My email is test@example.com"
    res = redactor.redact(text)
    assert "[REDACTED_EMAIL]" in res
    assert "test@example.com" not in res
