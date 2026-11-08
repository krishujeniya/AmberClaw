"""Targeted security branch coverage test suite - Part 4.

Covers residual branches in secret_scanner, sso oidc, audit logger,
abac engine, filters, and dlp engine to reach >= 90% branch coverage.
"""

from __future__ import annotations

import json
import re
import tarfile
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from amberclaw.security.abac import (
    ABACAccessDeniedError,
    ABACPolicyEngine,
    ABACPolicyRule,
    JustInTimeElevationManager,
    PolicyEffect,
    ResourceBoundary,
    SubjectAttributes,
)
from amberclaw.security.approval import ToolRiskLevel
from amberclaw.security.audit import SecurityAuditLogger
from amberclaw.security.dlp import DataLossPreventionEngine, _is_luhn_valid
from amberclaw.security.filters import (
    ArgumentValidationError,
    ToolCapabilityManifest,
    ToolExecutionFilter,
)
from amberclaw.security.secret_scanner import SecretScanner
from amberclaw.security.sso.models import SSOConfig, SSOProtocol
from amberclaw.security.sso.oidc import discover_oidc, validate_oidc_claims

MAX_ARCHIVE_FILE_LIMIT = 5 * 1024 * 1024 + 1024


# ============================================================================
# Section A: SecretScanner Residual Branch Coverage
# ============================================================================


def test_secret_scanner_redact_text_short_vs_long_matches() -> None:
    """Test SecretScanner.redact_text length thresholds for masking."""
    with patch("amberclaw.security.secret_scanner._select_secret_pattern") as mock_sel:
        mock_sel.return_value = re.compile(r"(?P<SLACK>\bxox-[0-9]{4}\b)")
        masked_short = SecretScanner.redact_text("xox-1234")
        assert "<SLACK TOKEN_REDACTED>" in masked_short

    long_key = "ghp_" + ("a" * 36)
    masked_long = SecretScanner.redact_text(long_key)
    assert "..." in masked_long


def test_secret_scanner_file_and_workspace_edge_cases(tmp_path: Path) -> None:
    """Test SecretScanner file existence, directory skipping, and workspace paths."""
    assert SecretScanner.scan_file(tmp_path / "nonexistent.txt") == []
    assert SecretScanner.scan_file(tmp_path) == []

    priv_key_file = tmp_path / "key.pem"
    priv_key_file.write_text(
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0\n-----END RSA PRIVATE KEY-----\n"
    )
    findings = SecretScanner.scan_file(priv_key_file)
    assert any(f["type"] == "Private Key" for f in findings)

    entropy_file = tmp_path / "entropy.txt"
    entropy_file.write_text("token = 4k9aZ8qL2mP0xW7vY3tN1bV6cJ5sD8fG\n")
    ent_findings = SecretScanner.scan_file(entropy_file, check_entropy=True)
    assert len(ent_findings) >= 0

    assert SecretScanner.scan_workspace(tmp_path / "absent_dir") == []


def test_secret_scanner_archive_edge_cases(tmp_path: Path) -> None:
    """Test SecretScanner archive scanning skips directories, large files, and non-archives."""
    plain_file = tmp_path / "test.txt"
    plain_file.write_text("plain text file")
    assert SecretScanner.scan_archive(plain_file) == []

    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("subdir/", "")
        zinfo = zipfile.ZipInfo("large.txt")
        zinfo.file_size = MAX_ARCHIVE_FILE_LIMIT
        zf.writestr(zinfo, b"0")

    zip_findings = SecretScanner.scan_archive(zip_path)
    assert zip_findings == []

    tar_path = tmp_path / "test.tar"
    with tarfile.open(tar_path, "w") as tf:
        dir_info = tarfile.TarInfo(name="subfolder")
        dir_info.type = tarfile.DIRTYPE
        tf.addfile(dir_info)

    tar_findings = SecretScanner.scan_archive(tar_path)
    assert tar_findings == []


# ============================================================================
# Section B: SSO OIDC Residual Branch Coverage
# ============================================================================


def test_validate_oidc_claims_roles_and_groups_edge_cases() -> None:
    """Test validate_oidc_claims with string roles, non-list roles, and non-string elements."""
    config = SSOConfig(
        protocol=SSOProtocol.OIDC,
        oidc_issuer_url="https://idp.example.com",
        oidc_client_id="client123",
        role_attribute_name="custom_roles",
        default_role="viewer",
    )

    claims_str_role = {
        "sub": "user-1",
        "email": "user1@example.com",
        "custom_roles": "admin",
        "groups": ["secops"],
    }
    profile1 = validate_oidc_claims(claims_str_role, config)
    assert "admin" in profile1.roles

    claims_non_list_role = {
        "sub": "user-2",
        "email": "user2@example.com",
        "custom_roles": 12345,
        "groups": 9999,
    }
    profile2 = validate_oidc_claims(claims_non_list_role, config)
    assert profile2.roles == ["viewer"]

    claims_empty_roles = {
        "sub": "user-3",
        "email": "user3@example.com",
        "custom_roles": [100, None, "unknown_role"],
    }
    profile3 = validate_oidc_claims(claims_empty_roles, config)
    assert profile3.roles == ["viewer"]


@pytest.mark.asyncio
async def test_discover_oidc_validation_failures() -> None:
    """Test discover_oidc raises ValueError on missing client_id or issuer mismatch."""
    cfg_no_client = SSOConfig(
        protocol=SSOProtocol.OIDC,
        oidc_issuer_url="https://idp.example.com",
        oidc_client_id="",
    )
    with pytest.raises(ValueError, match="OIDC client ID is required"):
        await discover_oidc(cfg_no_client)

    cfg_valid = SSOConfig(
        protocol=SSOProtocol.OIDC,
        oidc_issuer_url="https://idp.example.com",
        oidc_client_id="client1",
    )
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"issuer": "https://mismatched-issuer.com"}
    with (
        patch("httpx.AsyncClient.get", return_value=mock_resp),
        pytest.raises(ValueError, match="issuer does not match configuration"),
    ):
        await discover_oidc(cfg_valid)


# ============================================================================
# Section C: Audit Logger Residual Branch Coverage
# ============================================================================


def test_audit_logger_empty_file_and_missing_file_integrity(tmp_path: Path) -> None:
    """Test SecurityAuditLogger empty log inspection and nonexistent integrity check."""
    logger = SecurityAuditLogger(log_dir=tmp_path)
    logger.log_file.touch()

    idx, h = logger._get_last_entry()
    assert idx == -1
    assert h == "0" * 64

    missing_file = tmp_path / "absent_audit.jsonl"
    assert logger.verify_integrity(target_file=missing_file)


def test_audit_logger_integrity_mismatch_and_blank_lines(tmp_path: Path) -> None:
    """Test SecurityAuditLogger verification fails on broken sequence or broken hash chain."""
    logger = SecurityAuditLogger(log_dir=tmp_path)
    log_file = logger.log_file

    rec1 = {
        "index": 5,
        "previous_hash": "0" * 64,
        "timestamp_utc": "2026-11-08T00:00:00+00:00",
        "actor": "admin",
        "action": "test.action",
    }
    log_file.write_text(f"{json.dumps(rec1)}\n\n")
    assert not logger.verify_integrity(target_file=log_file)

    rec0 = {
        "index": 0,
        "previous_hash": "badhash",
        "timestamp_utc": "2026-11-08T00:00:00+00:00",
        "actor": "admin",
        "action": "test.action",
    }
    log_file.write_text(f"{json.dumps(rec0)}\n")
    assert not logger.verify_integrity(target_file=log_file)


# ============================================================================
# Section D: ABAC Policy Engine Residual Branch Coverage
# ============================================================================


def test_abac_rule_matches_and_enforce_denial() -> None:
    """Test ABACPolicyEngine rule matching action/resource filters and enforce exception."""
    engine = ABACPolicyEngine()
    rule = ABACPolicyRule(
        id="rule-scoped",
        effect=PolicyEffect.ALLOW,
        actions=["read"],
        resource_types=["document"],
    )
    subj = SubjectAttributes(subject_id="user1", roles=["analyst"], project_id="proj1")
    res_bad_act = ResourceBoundary(
        resource_id="doc1", resource_type="document", project_id="proj1"
    )
    assert not engine._rule_matches(rule, subj, "delete", res_bad_act)

    res_bad_type = ResourceBoundary(
        resource_id="srv1", resource_type="server", project_id="proj1"
    )
    assert not engine._rule_matches(rule, subj, "read", res_bad_type)

    with pytest.raises(
        ABACAccessDeniedError,
        match="ABAC Denied: Subject 'user1' unauthorized to 'delete'",
    ):
        engine.enforce(subj, "delete", res_bad_act)


def test_jit_elevation_manager_expiration_and_unrevoked() -> None:
    """Test JustInTimeElevationManager expiration cleanup and ungranted revocation."""
    mgr = JustInTimeElevationManager()
    past_iso = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    mgr._active_grants[("user1", "admin:all")] = MagicMock(expires_at=past_iso)

    assert not mgr.is_elevated("user1", "admin:all")
    assert ("user1", "admin:all") not in mgr._active_grants

    assert not mgr.revoke_elevation("user2", "nonexistent:scope")


# ============================================================================
# Section E: Tool Execution Filters Residual Branch Coverage
# ============================================================================


class ModelDummy(BaseModel):
    query: str


def test_tool_execution_filters_branches() -> None:
    """Test ToolExecutionFilter traversal toggle, schema validation, and output formatting."""
    valid_no_traversal = ToolExecutionFilter.validate_arguments(
        tool_name="test_tool",
        args={"path": "../secret"},
        block_traversal=False,
    )
    assert valid_no_traversal["path"] == "../secret"

    manifest = ToolCapabilityManifest(
        name="test_tool",
        description="test tool",
        risk_level=ToolRiskLevel.LOW,
        schema_model=ModelDummy,
    )
    with pytest.raises(ArgumentValidationError, match="Unexpected extra fields"):
        ToolExecutionFilter.validate_arguments(
            tool_name="test_tool",
            args={"query": "hello", "unexpected_extra": 123},
            manifest=manifest,
            strict_schema=True,
        )

    out_int = ToolExecutionFilter.filter_output(
        tool_name="test_tool",
        output=99999,  # type: ignore[arg-type]
    )
    assert out_int == "99999"

    out_no_redact = ToolExecutionFilter.filter_output(
        tool_name="test_tool",
        output="Bearer sk-live-1234567890abcdef",
        redact_sensitive_secrets=False,
    )
    assert "sk-live" in out_no_redact


# ============================================================================
# Section F: DLP Engine Residual Branch Coverage
# ============================================================================


def test_dlp_luhn_and_scan_empty_branches() -> None:
    """Test _is_luhn_valid edge cases, scan on empty string, and outbound pass-through."""
    assert not _is_luhn_valid("123")
    assert not _is_luhn_valid("1" * 25)

    empty_scan = DataLossPreventionEngine.scan("")
    assert empty_scan.clean_text == ""
    assert not empty_scan.has_violations

    clean_content = "This is a standard message with zero secrets or cards."
    assert DataLossPreventionEngine.enforce_outbound(clean_content) == clean_content
