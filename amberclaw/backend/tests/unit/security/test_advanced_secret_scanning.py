# ruff: noqa: PLR2004
"""Unit tests for Advanced Entropy-based and Deep Artifact Secret Scanning."""

import io
import tarfile
import zipfile
from pathlib import Path

from amberclaw.security.secret_scanner import SecretScanner


def test_shannon_entropy_calculation():
    # Empty string has 0 entropy
    assert SecretScanner.calculate_entropy("") == 0.0

    # Low entropy (repeated characters)
    low_ent = SecretScanner.calculate_entropy("aaaaaaaaaaaaaaaa")
    assert low_ent == 0.0

    # High entropy (random base64/hex credentials)
    high_ent = SecretScanner.calculate_entropy(
        "dGhpcyBpcyBhIHZlcnkgc2VjcmV0IHRva2VuISE="
    )
    assert high_ent > 4.0


def test_high_entropy_token_detection():
    # Ordinary English sentence
    clean_text = "The quick brown fox jumps over the lazy dog"
    assert len(SecretScanner.scan_entropy(clean_text)) == 0

    # UUID should be ignored
    uuid_text = "Transaction ID: 123e4567-e89b-12d3-a456-426614174000"
    assert len(SecretScanner.scan_entropy(uuid_text)) == 0

    # High-entropy random database password
    dirty_text = "DB_PASSWORD = 'xK9#mQ2$vL8!zP4*wR1^'"
    findings = SecretScanner.scan_entropy(dirty_text, threshold=3.5)
    assert len(findings) >= 1
    assert findings[0]["type"] == "High-Entropy Secret"
    assert findings[0]["entropy"] >= 3.5


def test_scan_text_with_entropy_flag():
    text = "Here is an unknown token: 7f8b9c0d1e2f3a4b5c6d7e8f"
    # Without entropy flag: regex only matches known vendor patterns
    f_without = SecretScanner.scan_text(text, check_entropy=False)
    assert len(f_without) == 0

    # With entropy flag: catches high-entropy unknown token
    f_with = SecretScanner.scan_text(text, check_entropy=True, entropy_threshold=3.5)
    assert len(f_with) >= 1
    assert f_with[0]["type"] == "High-Entropy Secret"


def test_deep_json_payload_scanning():
    trajectory_export = {
        "session_id": "ses_001",
        "turns": [
            {"role": "user", "content": "Hello agent"},
            {
                "role": "assistant",
                "metadata": {
                    "auth_header": "Bearer sk-ant-1234567890abcdef1234567890abcdef"
                },
            },
        ],
        "nested": {
            "config": {
                "admin_token": "ghp_" + "b" * 36,
            }
        },
    }

    findings = SecretScanner.scan_json_payload(trajectory_export)
    assert len(findings) == 2
    types = {f["type"] for f in findings}
    assert "Anthropic API Key" in types
    assert "GitHub Token" in types


def test_archive_scanning_zip_and_tar(tmp_path: Path):
    # 1. Test ZIP archive scanning
    zip_path = tmp_path / "test_bundle.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("safe.txt", "No secrets here\n")
        zf.writestr("leaked.env", "OPENAI_API_KEY=sk-" + "z" * 48 + "\n")

    zip_findings = SecretScanner.scan_archive(zip_path)
    assert len(zip_findings) == 1
    assert zip_findings[0]["source"] == "archive"
    assert zip_findings[0]["member"] == "leaked.env"
    assert zip_findings[0]["type"] == "OpenAI API Key"

    # 2. Test TAR.GZ archive scanning
    tar_path = tmp_path / "test_bundle.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        data = b"AWS_KEY=AKIA1234567890ABCDEF\n"
        ti = tarfile.TarInfo(name="credentials.conf")
        ti.size = len(data)
        tf.addfile(ti, io.BytesIO(data))

    tar_findings = SecretScanner.scan_archive(tar_path)
    assert len(tar_findings) == 1
    assert tar_findings[0]["source"] == "archive"
    assert tar_findings[0]["member"] == "credentials.conf"
    assert tar_findings[0]["type"] == "AWS Access Key ID"
