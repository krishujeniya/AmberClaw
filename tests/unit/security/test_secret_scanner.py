"""Unit tests for the SecretScanner security component."""

from pathlib import Path

from amberclaw.security.secret_scanner import SecretScanner


def test_scan_and_redact_openai_key():
    key = "sk-" + "a" * 48
    text = f"Here is my openai key: {key}."
    findings = SecretScanner.scan_text(text)
    assert len(findings) == 1
    assert findings[0]["type"] == "OpenAI API Key"
    assert findings[0]["match"] == key

    redacted = SecretScanner.redact_text(text)
    assert key not in redacted
    assert "sk-aaa...aaaa" in redacted


def test_scan_and_redact_anthropic_key():
    key = "sk-ant-1234567890abcdef1234567890abcdef"
    text = f"My anthropic key is {key}"
    findings = SecretScanner.scan_text(text)
    assert len(findings) == 1
    assert findings[0]["type"] == "Anthropic API Key"
    assert findings[0]["match"] == key

    redacted = SecretScanner.redact_text(text)
    assert key not in redacted
    assert "sk-ant...cdef" in redacted


def test_scan_and_redact_google_key():
    key = "AIzaSy" + "A" * 33
    text = f"My google key is {key}"
    findings = SecretScanner.scan_text(text)
    assert len(findings) == 1
    assert findings[0]["type"] == "Google API Key"
    assert findings[0]["match"] == key

    redacted = SecretScanner.redact_text(text)
    assert key not in redacted
    assert "AIzaSy...AAAA" in redacted


def test_scan_and_redact_github_token():
    key = "ghp_" + "a" * 36
    text = f"My github key is {key}"
    findings = SecretScanner.scan_text(text)
    assert len(findings) == 1
    assert findings[0]["type"] == "GitHub Token"
    assert findings[0]["match"] == key

    redacted = SecretScanner.redact_text(text)
    assert key not in redacted
    assert "ghp_aa...aaaa" in redacted


def test_scan_and_redact_slack_token():
    key = "xoxb-1234567890-abcdefghij"
    text = f"My slack key is {key}"
    findings = SecretScanner.scan_text(text)
    assert len(findings) == 1
    assert findings[0]["type"] == "Slack Token"
    assert findings[0]["match"] == key

    redacted = SecretScanner.redact_text(text)
    assert key not in redacted
    assert "xoxb-1...ghij" in redacted


def test_scan_and_redact_aws_key():
    key = "AKIA1234567890ABCDEF"
    text = f"My aws key is {key}"
    findings = SecretScanner.scan_text(text)
    assert len(findings) == 1
    assert findings[0]["type"] == "AWS Access Key ID"
    assert findings[0]["match"] == key

    redacted = SecretScanner.redact_text(text)
    assert key not in redacted
    assert "AKIA12...CDEF" in redacted


def test_scan_and_redact_private_key():
    key = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA0G...rest of private key...\n"
        "-----END RSA PRIVATE KEY-----"
    )
    text = f"Warning: do not share this:\n{key}"
    findings = SecretScanner.scan_text(text)
    assert len(findings) == 1
    assert findings[0]["type"] == "Private Key"
    assert findings[0]["match"] == key

    redacted = SecretScanner.redact_text(text)
    assert key not in redacted
    assert "<PRIVATE KEY_REDACTED>" in redacted


def test_scan_file_and_workspace(tmp_path: Path):
    # Create test directory structure
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    file_clean = src_dir / "clean.py"
    file_clean.write_text("def run():\n    print('Hello World')\n")

    file_dirty = src_dir / "dirty.py"
    file_dirty.write_text(
        "import os\nOPENAI_KEY = 'sk-" + "a" * 48 + "'\nprint('Config loaded')\n"
    )

    # Check scan_file
    dirty_findings = SecretScanner.scan_file(file_dirty)
    assert len(dirty_findings) == 1
    assert dirty_findings[0]["line"] == 2  # noqa: PLR2004
    assert dirty_findings[0]["type"] == "OpenAI API Key"

    clean_findings = SecretScanner.scan_file(file_clean)
    assert len(clean_findings) == 0

    # Check scan_workspace
    all_findings = SecretScanner.scan_workspace(tmp_path)
    assert len(all_findings) == 1
    assert all_findings[0]["file"] == str(file_dirty)

    # Test exclusion
    excluded_findings = SecretScanner.scan_workspace(tmp_path, exclude_patterns={"src"})
    assert len(excluded_findings) == 0


def test_redact_text_covers_all_secret_families():
    secrets = [
        "sk-" + "a" * 48,
        "sk-ant-" + "b" * 32,
        "AIzaSy" + "C" * 33,
        "ghp_" + "d" * 36,
        "xoxb-" + "1" * 12,
        "AKIA" + "E" * 16,
        "-----BEGIN RSA PRIVATE KEY-----\nsecret\n-----END RSA PRIVATE KEY-----",
    ]

    redacted = SecretScanner.redact_text(" | ".join(secrets))

    for secret in secrets:
        assert secret not in redacted
    assert redacted.count("<PRIVATE KEY_REDACTED>") == 1


def test_redact_text_pattern_cache_handles_new_family_later():
    openai_key = "sk-" + "a" * 48
    google_key = "AIzaSy" + "B" * 33

    assert openai_key not in SecretScanner.redact_text(openai_key)
    # A later call introducing a different family must still redact it.
    assert google_key not in SecretScanner.redact_text(google_key)

    both = SecretScanner.redact_text(f"{openai_key} and {google_key}")
    assert openai_key not in both
    assert google_key not in both
