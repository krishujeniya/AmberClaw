import pytest
from amberclaw.security.pii import PIIRedactor


def test_pii_redactor_emails() -> None:
    redactor = PIIRedactor()
    text = "Hello, my email is john.doe@example.com. Please write to contact@test.co.uk."
    redacted = redactor.redact(text)
    assert "john.doe@example.com" not in redacted
    assert "contact@test.co.uk" not in redacted
    assert redacted.count("[REDACTED_EMAIL]") == 2


def test_pii_redactor_ips() -> None:
    redactor = PIIRedactor()
    text = "Server running on 192.168.1.1 and 10.0.0.138."
    redacted = redactor.redact(text)
    assert "192.168.1.1" not in redacted
    assert "10.0.0.138" not in redacted
    assert redacted.count("[REDACTED_IP]") == 2


def test_pii_redactor_phones() -> None:
    redactor = PIIRedactor()
    text = "Call me at +1-123-456-7890 or 123-456-7890."
    redacted = redactor.redact(text)
    assert "123-456-7890" not in redacted
    assert redacted.count("[REDACTED_PHONE]") == 2


def test_pii_redactor_credit_cards() -> None:
    redactor = PIIRedactor()
    text = "Visa card: 4111 1111 1111 1111."
    redacted = redactor.redact(text)
    assert "4111" not in redacted
    assert "[REDACTED_CARD]" in redacted
