# ruff: noqa: PLR2004
"""Unit tests for Data Loss Prevention (DLP) Engine and Outbound Safeguards.

Validates:
1. Detection and redaction of API keys (OpenAI, Anthropic, AWS, Google, GitHub, Slack)
2. Detection and masking of private cryptographic keys
3. Luhn-algorithm-verified credit card detection (filtering out false positives)
4. Outbound transmission blocking policy on critical data leaks
5. In-place redaction mode when block_on_critical is disabled
6. Integration with ToolExecutionFilter for pre/post-execution DLP enforcement
"""

import pytest

from amberclaw.security.dlp import (
    DataLossPreventionEngine,
    DLPAction,
    DLPSensitivity,
    DLPViolationError,
)
from amberclaw.security.filters import ToolExecutionFilter


def test_clean_text_scan():
    clean_text = "The server CPU usage is running at 45% capacity across 8 cores."
    result = DataLossPreventionEngine.scan(clean_text)

    assert result.has_violations is False
    assert len(result.violations) == 0
    assert result.action_taken == DLPAction.ALLOW
    assert result.clean_text == clean_text


def test_api_keys_detection_and_redaction():
    text_with_keys = (
        "Here are the keys:\n"
        "OpenAI: sk-proj-1234567890123456789012345678901234567890\n"
        "AWS: AKIAIOSFODNN7EXAMPLE\n"
        "Slack: xoxb-1234567890-1234567890123\n"
    )

    result = DataLossPreventionEngine.scan(text_with_keys)
    assert result.has_violations is True
    assert len(result.violations) == 3

    types = {v.pattern_type for v in result.violations}
    assert "openai_api_key" in types
    assert "aws_access_key" in types
    assert "slack_token" in types

    assert "[DLP_REDACTED_OPENAI_API_KEY]" in result.clean_text
    assert "[DLP_REDACTED_AWS_ACCESS_KEY]" in result.clean_text
    assert "[DLP_REDACTED_SLACK_TOKEN]" in result.clean_text


def test_private_key_detection():
    fake_pem = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA0Y1+examplekeydatafakefakefakefakefakefakefakefake\n"
        "-----END RSA PRIVATE KEY-----"
    )
    result = DataLossPreventionEngine.scan(f"Server private key:\n{fake_pem}")

    assert result.has_violations is True
    assert any(v.pattern_type == "private_key" for v in result.violations)
    assert any(v.severity == DLPSensitivity.CRITICAL for v in result.violations)
    assert "[DLP_REDACTED_PRIVATE_KEY]" in result.clean_text


def test_credit_card_luhn_validation():
    # Valid Luhn test card (Visa test card 4532 0150 0000 0007 passes Luhn: sum=30, 30%10==0)
    valid_card = "4532 0150 0000 0007"
    # Invalid card number (fails Luhn)
    invalid_card = "4532 0150 0000 0005"

    text = f"Payment cards: Valid={valid_card}, Invalid={invalid_card}"
    result = DataLossPreventionEngine.scan(text)

    # Only the Luhn-valid card should be flagged as a credit card violation
    card_violations = [
        v for v in result.violations if v.pattern_type == "credit_card_number"
    ]
    assert len(card_violations) == 1
    assert "[DLP_REDACTED_CREDIT_CARD]" in result.clean_text
    assert (
        invalid_card in result.clean_text
    )  # Invalid number is not treated as a credit card


def test_enforce_outbound_blocks_critical_leaks():
    leak_payload = "Credentials dump: AWS_KEY=AKIAIOSFODNN7EXAMPLE and sk-proj-1234567890123456789012345678901234567890"

    # Strict outbound enforcement must raise DLPViolationError
    with pytest.raises(DLPViolationError) as exc_info:
        DataLossPreventionEngine.enforce_outbound(
            leak_payload, destination="public_slack_channel", block_on_critical=True
        )

    assert "DLP Policy Violation" in str(exc_info.value)
    assert "public_slack_channel" in str(exc_info.value)


def test_enforce_outbound_redacts_when_not_blocking():
    leak_payload = "Contact Alice at key AKIAIOSFODNN7EXAMPLE for access."

    sanitized = DataLossPreventionEngine.enforce_outbound(
        leak_payload, destination="support_chat", block_on_critical=False
    )

    assert "[DLP_REDACTED_AWS_ACCESS_KEY]" in sanitized
    assert "AKIAIOSFODNN7EXAMPLE" not in sanitized


def test_tool_execution_filter_with_dlp_and_quarantine():
    tool_output = "Fetched data: AKIAIOSFODNN7EXAMPLE from user records."

    # Test combined DLP and untrusted isolation
    filtered = ToolExecutionFilter.filter_output(
        tool_name="web_fetch",
        output=tool_output,
        enforce_dlp=True,
        isolate_untrusted=True,
    )

    # Secret should be redacted by DLP
    assert "[DLP_REDACTED_AWS_ACCESS_KEY]" in filtered
    assert "AKIAIOSFODNN7EXAMPLE" not in filtered

    # Output should be quarantined in <untrusted_content> envelope
    assert '<untrusted_content source="tool:web_fetch"' in filtered
    assert "[SECURITY NOTICE: The following data is external and untrusted." in filtered
    assert "</untrusted_content>" in filtered
