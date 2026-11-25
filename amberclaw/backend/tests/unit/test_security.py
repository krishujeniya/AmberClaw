# ruff: noqa: PLR2004
"""Unit tests verifying the amberclaw.security public facade and integration."""

import os

from amberclaw.security import (
    ApprovalStatus,
    ResourceLimits,
    SecretScanner,
    SecretVault,
    SecurityCompromiseError,
    SecurityModuleConfig,
    ToolCapabilityManifest,
    ToolRiskLevel,
    resolved_secrets_context,
)


def test_security_module_config():
    cfg = SecurityModuleConfig()
    assert cfg.enabled is True
    assert "2026" in cfg.version


def test_security_public_exports_and_types():
    assert issubclass(SecurityCompromiseError, PermissionError)
    assert ToolRiskLevel.CRITICAL == "critical"
    assert ApprovalStatus.APPROVED == "approved"


def test_vault_and_secrets_context(tmp_path):
    test_vault = SecretVault(key_dir=tmp_path)
    test_vault.store_secret("API_TOKEN", "super-secret-value-1234")

    val = test_vault.get_secret("API_TOKEN")
    assert val == "super-secret-value-1234"

    # Context resolution
    with resolved_secrets_context("plain-token-val", env_vars=["TEST_ENV_INJECT"]):
        assert "TEST_ENV_INJECT" in os.environ


def test_secret_scanner_detection(tmp_path):
    scanner = SecretScanner()
    file_with_secret = tmp_path / "leak.env"
    file_with_secret.write_text(
        "GITHUB_TOKEN=ghp_123456789012345678901234567890123456\n"
    )

    findings = scanner.scan_file(file_with_secret)
    assert len(findings) > 0
    assert any("github" in f.get("type", "").lower() for f in findings)


def test_resource_limits_configuration():
    limits = ResourceLimits(
        max_cpu_seconds=15,
        max_memory_bytes=256 * 1024 * 1024,
    )
    assert limits.max_cpu_seconds == 15
    assert limits.max_memory_bytes == 268435456


def test_tool_safety_and_capability_manifest():
    manifest = ToolCapabilityManifest(
        name="secure_query",
        risk_level=ToolRiskLevel.READ_ONLY,
        is_mutating=False,
        required_scopes=["query:read"],
    )
    assert manifest.name == "secure_query"
    assert manifest.risk_level == ToolRiskLevel.READ_ONLY
    assert manifest.is_mutating is False
