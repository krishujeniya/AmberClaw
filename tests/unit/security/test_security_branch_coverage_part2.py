"""Secondary branch coverage tests for security subsystems.

Tests edge cases in network_policy, mtls, vault, and oidc.
"""

from __future__ import annotations

import io
import json
import socket
import tarfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from amberclaw.security.mtls import (
    MTLSConfig,
    MTLSSecurityError,
    create_client_ssl_context,
    create_server_ssl_context,
    generate_mtls_test_pki,
    verify_peer_identity,
)
from amberclaw.security.network_policy import HTTPS_PORT, NetworkPolicy
from amberclaw.security.sandbox import (
    CodeSandbox,
    DecompressionGuard,
    DecompressionSecurityError,
    EphemeralFilesystemSandbox,
    HostSocketAndMetadataFilter,
    apply_seccomp_filters,
)
from amberclaw.security.secret_scanner import SecretScanner
from amberclaw.security.sso.models import SSOConfig, SSOProtocol
from amberclaw.security.sso.oidc import (
    _https_endpoint,
    build_oidc_auth_url,
    validate_oidc_claims,
)
from amberclaw.security.vault import SecretVault

# ==============================================================================
# Network Policy Tests
# ==============================================================================


def test_network_policy_load_yaml_missing(tmp_path: Path) -> None:
    non_existent = tmp_path / "does_not_exist.yaml"
    policy = NetworkPolicy.load_from_yaml(non_existent)
    assert "*.openai.com" in policy.allowed_hosts


def test_network_policy_load_yaml_corrupted(tmp_path: Path) -> None:
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("invalid: [yaml: broken", encoding="utf-8")
    policy = NetworkPolicy.load_from_yaml(bad_yaml)
    assert "*.openai.com" in policy.allowed_hosts


def test_network_policy_load_yaml_valid(tmp_path: Path) -> None:
    valid_yaml = tmp_path / "policy.yaml"
    payload = {
        "allowed_hosts": ["*.internal.net", "custom.domain.org"],
        "allowed_ports": [443, 8443],
        "enforce_tls_only": True,
        "binary_rules": {
            "curl": {
                "allowed_hosts": ["custom.domain.org"],
                "allowed_ports": [443],
            }
        },
    }
    valid_yaml.write_text(json.dumps(payload), encoding="utf-8")
    policy = NetworkPolicy.load_from_yaml(valid_yaml)
    assert policy.enforce_tls_only is True
    assert policy.is_allowed("sub.internal.net", 443) is True
    assert policy.is_allowed("custom.domain.org", 443) is True
    assert policy.is_allowed("custom.domain.org", 8443) is False
    assert policy.is_allowed("custom.domain.org", 80) is False


def test_network_policy_binary_context_evaluation() -> None:
    policy = NetworkPolicy.default_policy()
    # git binary allowed to github.com on 443
    assert policy.is_allowed("github.com", HTTPS_PORT, binary_context="git") is True
    # git binary rejected on port 80
    assert policy.is_allowed("github.com", 80, binary_context="git") is False
    # git binary rejected for api.tavily.com
    assert (
        policy.is_allowed("api.tavily.com", HTTPS_PORT, binary_context="git") is False
    )


def test_network_policy_tls_enforcement() -> None:
    policy = NetworkPolicy(
        allowed_hosts=["example.com"],
        allowed_ports=[80, HTTPS_PORT],
        enforce_tls_only=True,
    )
    assert policy.is_allowed("example.com", HTTPS_PORT) is True
    assert policy.is_allowed("example.com", 80) is False


# ==============================================================================
# mTLS Tests
# ==============================================================================


def test_mtls_missing_files_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.pem"
    existing = tmp_path / "existing.pem"
    existing.write_text("dummy", encoding="utf-8")

    cfg = MTLSConfig(
        ca_cert_path=missing,
        cert_path=existing,
        key_path=existing,
    )
    with pytest.raises(MTLSSecurityError, match="CA certificate file not found"):
        create_server_ssl_context(cfg)

    cfg2 = MTLSConfig(
        ca_cert_path=existing,
        cert_path=missing,
        key_path=existing,
    )
    with pytest.raises(MTLSSecurityError, match="Server certificate file not found"):
        create_server_ssl_context(cfg2)

    cfg3 = MTLSConfig(
        ca_cert_path=existing,
        cert_path=existing,
        key_path=missing,
    )
    with pytest.raises(MTLSSecurityError, match="Server private key file not found"):
        create_server_ssl_context(cfg3)


def test_mtls_client_missing_files_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.pem"
    existing = tmp_path / "existing.pem"
    existing.write_text("dummy", encoding="utf-8")

    cfg = MTLSConfig(
        ca_cert_path=missing,
        cert_path=existing,
        key_path=existing,
    )
    with pytest.raises(MTLSSecurityError, match="CA certificate file not found"):
        create_client_ssl_context(cfg)

    cfg2 = MTLSConfig(
        ca_cert_path=existing,
        cert_path=missing,
        key_path=existing,
    )
    with pytest.raises(MTLSSecurityError, match="Client certificate file not found"):
        create_client_ssl_context(cfg2)

    cfg3 = MTLSConfig(
        ca_cert_path=existing,
        cert_path=existing,
        key_path=missing,
    )
    with pytest.raises(MTLSSecurityError, match="Client private key file not found"):
        create_client_ssl_context(cfg3)


def test_mtls_context_with_ciphers_and_no_verify(tmp_path: Path) -> None:
    pki = generate_mtls_test_pki(tmp_path / "pki")
    cfg = MTLSConfig(
        ca_cert_path=pki["ca_cert"],
        cert_path=pki["server_cert"],
        key_path=pki["server_key"],
        verify_peer=False,
    )
    srv_ctx = create_server_ssl_context(cfg)
    assert srv_ctx is not None

    cli_cfg = MTLSConfig(
        ca_cert_path=pki["ca_cert"],
        cert_path=pki["client_cert"],
        key_path=pki["client_key"],
        verify_peer=False,
    )
    cli_ctx = create_client_ssl_context(cli_cfg)
    assert cli_ctx is not None


def test_mtls_verify_peer_identity_cases() -> None:
    assert verify_peer_identity(None) is False

    cert_data = {
        "subject": ((("commonName", "allowed-worker"),),),
        "subjectAltName": (("DNS", "cluster.local"), ("DNS", "worker.cluster")),
    }
    # No allowlist specified means any peer is accepted
    assert verify_peer_identity(cert_data, None) is True
    assert verify_peer_identity(cert_data, []) is True

    # CN match
    assert verify_peer_identity(cert_data, ["allowed-worker"]) is True
    # SAN match
    assert verify_peer_identity(cert_data, ["worker.cluster"]) is True
    # Rejection
    assert verify_peer_identity(cert_data, ["unauthorized-node"]) is False


# ==============================================================================
# Vault Tests
# ==============================================================================


def test_vault_invalid_env_key_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AMBERCLAW_VAULT_KEY", "invalid_base64_key")
    vault = SecretVault(key_dir=tmp_path)
    # Should fall back to creating a file-based or memory key without blowing up
    vault.store_secret("key1", "val1")
    assert vault.get_secret("key1") == "val1"


def test_vault_corrupted_key_file_falls_back(tmp_path: Path) -> None:
    key_file = tmp_path / ".vault_key"
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_text("corrupted_key_content", encoding="utf-8")

    vault = SecretVault(key_dir=tmp_path)
    vault.store_secret("key1", "val1")
    assert vault.get_secret("key1") == "val1"


def test_vault_corrupted_payload_returns_empty(tmp_path: Path) -> None:
    vault = SecretVault(key_dir=tmp_path)
    vault.store_secret("k1", "v1")

    # Overwrite payload with invalid ciphertext
    vault.vault_file.write_bytes(b"corrupted_bytes_that_fail_fernet")
    assert vault.get_secret("k1") is None


def test_vault_malformed_json_types(tmp_path: Path) -> None:
    vault = SecretVault(key_dir=tmp_path)
    fernet = vault._get_fernet()

    # Payload is a list instead of a dict
    bad_payload = fernet.encrypt(json.dumps([1, 2, 3]).encode("utf-8"))
    vault.vault_file.write_bytes(bad_payload)
    assert vault._load_vault_data() == {}

    # Dict with non-string values
    bad_values = fernet.encrypt(json.dumps({"key": 12345}).encode("utf-8"))
    vault.vault_file.write_bytes(bad_values)
    assert vault._load_vault_data() == {}


def test_vault_rotation_hook_exception_safety(tmp_path: Path) -> None:
    vault = SecretVault(key_dir=tmp_path)

    failing_hook = MagicMock(side_effect=RuntimeError("hook execution blew up"))
    vault.register_rotation_hook("api_key", failing_hook)

    # Storing secret should not raise despite hook error
    vault.store_secret("api_key", "secret_value_123")
    assert vault.get_secret("api_key") == "secret_value_123"
    failing_hook.assert_called_once_with("secret_value_123")


# ==============================================================================
# SSO / OIDC Tests
# ==============================================================================


def test_oidc_build_auth_url() -> None:
    cfg = SSOConfig(
        protocol=SSOProtocol.OIDC,
        oidc_issuer_url="https://idp.local",
        oidc_client_id="test_client",
        sp_acs_url="https://app.local/callback",
    )
    url = build_oidc_auth_url(cfg, state="s123", nonce="n456")
    assert "https://idp.local/protocol/openid-connect/auth" in url
    assert "client_id=test_client" in url
    assert "state=s123" in url
    assert "nonce=n456" in url


def test_oidc_validate_claims_missing_identity() -> None:
    cfg = SSOConfig(protocol=SSOProtocol.OIDC)
    with pytest.raises(ValueError, match="OIDC Claims missing 'sub' and 'email'"):
        validate_oidc_claims({}, cfg)


def test_oidc_validate_claims_success() -> None:
    cfg = SSOConfig(
        protocol=SSOProtocol.OIDC,
        role_attribute_name="custom_roles",
    )
    claims = {
        "sub": "user_123",
        "email": "user@enterprise.org",
        "name": "Jane Doe",
        "given_name": "Jane",
        "family_name": "Doe",
        "custom_roles": ["Admin", "unrecognized"],
        "groups": ["sec-ops"],
    }
    profile = validate_oidc_claims(claims, cfg)
    assert profile.user_id == "user_123"
    assert profile.email == "user@enterprise.org"
    assert "admin" in profile.roles
    assert "sec-ops" in profile.groups


def test_oidc_https_endpoint_validation() -> None:
    # Valid
    assert (
        _https_endpoint("https://idp.enterprise.com/oauth2")
        == "https://idp.enterprise.com/oauth2"
    )

    # Missing / non-string
    with pytest.raises(ValueError, match="OIDC discovery endpoint is missing"):
        _https_endpoint(None)

    # HTTP not allowed
    with pytest.raises(ValueError, match="must use HTTPS"):
        _https_endpoint("http://idp.enterprise.com/oauth2")

    # Userinfo not allowed
    with pytest.raises(ValueError, match="must use HTTPS"):
        _https_endpoint("https://user:pass@idp.enterprise.com/oauth2")

    # Fragment not allowed
    with pytest.raises(ValueError, match="must use HTTPS"):
        _https_endpoint("https://idp.enterprise.com/oauth2#frag")


# ==============================================================================
# Secret Scanner Tests
# ==============================================================================


def test_secret_scanner_git_history_no_git(tmp_path: Path) -> None:
    findings = SecretScanner.scan_git_history(tmp_path)
    assert findings == []


def test_secret_scanner_git_history_with_commits(tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir(parents=True)

    git_output = (
        "commit a1b2c3d4e5f67890\n"
        "Author: dev <dev@local>\n"
        "Date: today\n\n"
        "+++ b/src/config.py\n"
        '+AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n'
        '-OLD_KEY = "dummy"\n'
    )
    mock_run = MagicMock(return_value=SimpleNamespace(returncode=0, stdout=git_output))
    with patch("subprocess.run", mock_run):
        findings = SecretScanner.scan_git_history(tmp_path)
        assert len(findings) > 0
        assert findings[0]["source"] == "git_history"
        assert findings[0]["commit"] == "a1b2c3d4e5"
        assert findings[0]["file"] == "src/config.py"


def test_secret_scanner_archive_missing(tmp_path: Path) -> None:
    assert SecretScanner.scan_archive(tmp_path / "missing.zip") == []


def test_secret_scanner_archive_zip_and_tar(tmp_path: Path) -> None:
    # 1. Zip archive with secret
    zip_path = tmp_path / "secrets.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("credentials.env", 'KEY="AKIAIOSFODNN7EXAMPLE"\n')
    zip_findings = SecretScanner.scan_archive(zip_path)
    assert len(zip_findings) > 0
    assert zip_findings[0]["source"] == "archive"
    assert zip_findings[0]["archive"] == "secrets.zip"

    # 2. Tar archive with secret
    tar_path = tmp_path / "secrets.tar"
    with tarfile.open(tar_path, "w") as tf:
        data = b'export AWS_ACCESS_KEY_ID="AKIAIOSFODNN7EXAMPLE"\n'
        ti = tarfile.TarInfo("env.sh")
        ti.size = len(data)
        tf.addfile(ti, io.BytesIO(data))
    tar_findings = SecretScanner.scan_archive(tar_path)
    assert len(tar_findings) > 0
    assert tar_findings[0]["source"] == "archive"
    assert tar_findings[0]["archive"] == "secrets.tar"


def test_secret_scanner_json_payload() -> None:
    payload = {
        "user": {"name": "Alice"},
        "configs": [
            {"provider": "aws", "key": "AKIAIOSFODNN7EXAMPLE"},
            {"provider": "local", "port": 8080},
        ],
    }
    findings = SecretScanner.scan_json_payload(payload)
    assert len(findings) > 0
    assert findings[0]["path"] == "$.configs[0].key"


def test_secret_scanner_entropy_filters() -> None:
    # Digit string should be skipped
    assert SecretScanner.scan_entropy("12345678901234567890") == []
    # Standard UUID format should be skipped
    assert SecretScanner.scan_entropy("12345678-1234-1234-1234-123456789012") == []
    # Lowercase alphabetic should be skipped
    assert SecretScanner.scan_entropy("abcdefghijklmnopqrstuvwxyz") == []
    # High entropy token should be detected
    high_ent = "xK9#mQ2$vL5*pW8&jR1@"
    findings = SecretScanner.scan_entropy(high_ent, min_length=15, threshold=3.5)
    assert len(findings) > 0


# ==============================================================================
# Sandbox Lifecycle Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_sandbox_docker_lifecycle_and_execution() -> None:
    sandbox = CodeSandbox(use_docker=True)
    mock_backend = AsyncMock()
    mock_backend.start = AsyncMock()
    mock_backend.stop = AsyncMock()
    mock_backend.execute_python = AsyncMock(
        return_value={
            "stdout": "hello",
            "stderr": "",
            "exit_code": 0,
            "execution_time_ms": 15.0,
        }
    )
    mock_backend.execute_bash = AsyncMock(
        return_value={
            "stdout": "ok",
            "stderr": "",
            "exit_code": 0,
            "execution_time_ms": 10.0,
        }
    )
    sandbox._docker_backend = mock_backend

    async with sandbox as sb:
        res_py = await sb.execute_python("print('hello')")
        assert res_py.stdout == "hello"
        assert res_py.exit_code == 0

        res_sh = await sb.execute_bash("echo ok")
        assert res_sh.stdout == "ok"
        assert res_sh.exit_code == 0

    mock_backend.start.assert_awaited_once()
    mock_backend.stop.assert_awaited_once()


def test_seccomp_filters_architectures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("platform.system", lambda: "Linux")
    mock_libc = MagicMock()
    mock_libc.prctl.return_value = 0
    monkeypatch.setattr("ctypes.CDLL", lambda *_: mock_libc)

    # 1. x86_64
    monkeypatch.setattr("platform.machine", lambda: "x86_64")
    assert apply_seccomp_filters() is True

    # 2. arm64
    monkeypatch.setattr("platform.machine", lambda: "aarch64")
    assert apply_seccomp_filters() is True

    # 3. unsupported arch
    monkeypatch.setattr("platform.machine", lambda: "mips64")
    assert apply_seccomp_filters() is False


def test_ephemeral_filesystem_sandbox_traversal() -> None:
    sb = EphemeralFilesystemSandbox()
    with pytest.raises(RuntimeError, match="not initialized"):
        sb.resolve_safe_path("foo.txt")

    with sb:
        safe_p = sb.resolve_safe_path("allowed.txt")
        assert safe_p.parent == sb.path

        with pytest.raises(PermissionError, match="Path traversal detected"):
            sb.resolve_safe_path("../../../etc/passwd")


def test_decompression_guard_tar_symlink(tmp_path: Path) -> None:
    tar_path = tmp_path / "symlink.tar"
    with tarfile.open(tar_path, "w") as tf:
        ti = tarfile.TarInfo("link_to_root")
        ti.type = tarfile.SYMTYPE
        ti.linkname = "/etc/passwd"
        tf.addfile(ti)

    with pytest.raises(DecompressionSecurityError, match="Symlinks and hardlinks"):
        DecompressionGuard.extract_tar(tar_path, tmp_path / "dest")


def test_host_socket_and_metadata_dns_filtering() -> None:
    # Forbidden hostname
    assert (
        HostSocketAndMetadataFilter.verify_destination_host("169.254.169.254") is False
    )
    assert (
        HostSocketAndMetadataFilter.verify_destination_host("metadata.google.internal")
        is False
    )

    # DNS failure
    with patch("socket.getaddrinfo", side_effect=socket.gaierror("lookup failed")):
        assert (
            HostSocketAndMetadataFilter.verify_destination_host("unknown.domain.org")
            is False
        )


def test_decompression_guard_extract_successful_nested(tmp_path: Path) -> None:
    # 1. Tar extraction with directory and regular file
    tar_path = tmp_path / "nested.tar"
    with tarfile.open(tar_path, "w") as tf:
        dir_info = tarfile.TarInfo("subdir")
        dir_info.type = tarfile.DIRTYPE
        tf.addfile(dir_info)

        file_info = tarfile.TarInfo("subdir/file.txt")
        content = b"hello tar content\n"
        file_info.size = len(content)
        tf.addfile(file_info, io.BytesIO(content))

    out_tar = tmp_path / "tar_extracted"
    paths_tar = DecompressionGuard.extract_tar(tar_path, out_tar)
    assert len(paths_tar) == 1
    assert (out_tar / "subdir" / "file.txt").read_bytes() == content

    # 2. Zip extraction with directory and regular file
    zip_path = tmp_path / "nested.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("zipdir/", "")
        zf.writestr("zipdir/file.txt", "hello zip content\n")

    out_zip = tmp_path / "zip_extracted"
    paths_zip = DecompressionGuard.extract_zip(zip_path, out_zip)
    assert len(paths_zip) == 1
    assert (out_zip / "zipdir" / "file.txt").read_text(
        encoding="utf-8"
    ) == "hello zip content\n"


def test_decompression_guard_zip_symlink(tmp_path: Path) -> None:
    zip_path = tmp_path / "symlink.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zi = zipfile.ZipInfo("symlink_file")
        # 0o120777 << 16 marks S_IFLNK in external_attr
        zi.external_attr = 0o120777 << 16
        zf.writestr(zi, "/etc/passwd")

    with pytest.raises(DecompressionSecurityError, match="Symlinks inside archives"):
        DecompressionGuard.extract_zip(zip_path, tmp_path / "dest_zip")


def test_host_socket_and_metadata_redirect_ssrf() -> None:
    with pytest.raises(PermissionError, match="Prohibited redirect scheme"):
        HostSocketAndMetadataFilter.verify_redirect_url("ftp://127.0.0.1/file")

    with pytest.raises(PermissionError, match="Redirect URL missing hostname"):
        HostSocketAndMetadataFilter.verify_redirect_url("https:///missing")

    # Destination host resolves to private IP
    with (
        patch.object(
            HostSocketAndMetadataFilter, "verify_destination_host", return_value=False
        ),
        pytest.raises(PermissionError, match="Prohibited SSRF destination"),
    ):
        HostSocketAndMetadataFilter.verify_redirect_url("https://forbidden.local/api")

    # Safe public URL
    with patch.object(
        HostSocketAndMetadataFilter, "verify_destination_host", return_value=True
    ):
        safe_url = HostSocketAndMetadataFilter.verify_redirect_url(
            "https://api.openai.com/v1"
        )
        assert safe_url == "https://api.openai.com/v1"


def test_secret_scanner_git_history_and_archive_edges(tmp_path: Path) -> None:
    # 1. subprocess.run exception in git history
    git_dir = tmp_path / ".git"
    git_dir.mkdir(parents=True, exist_ok=True)
    with patch("subprocess.run", side_effect=OSError("git not found")):
        assert SecretScanner.scan_git_history(tmp_path) == []

    # 2. Archive skipping oversized files (> 5MB)
    tar_path = tmp_path / "large.tar"
    large_payload = b"0" * (6 * 1024 * 1024)
    with tarfile.open(tar_path, "w") as tf:
        large_info = tarfile.TarInfo("large.bin")
        large_info.size = len(large_payload)
        tf.addfile(large_info, io.BytesIO(large_payload))
    assert SecretScanner.scan_archive(tar_path) == []

    zip_path = tmp_path / "large.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zi = zipfile.ZipInfo("large.bin")
        zi.file_size = 10 * 1024 * 1024
        zf.writestr(zi, b"")
    assert SecretScanner.scan_archive(zip_path) == []
