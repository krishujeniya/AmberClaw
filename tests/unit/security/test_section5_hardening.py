"""Comprehensive unit tests for Section 5 security upgrades:
mTLS, Hardware MFA, Memory Zeroing, Sandbox Hardening, Policy Lock,
External Transmission Confirmation, and Data Retention / Legal Hold.
"""

# ruff: noqa: S105, PLR2004, ARG005
from __future__ import annotations

import base64
import hashlib
import hmac as py_hmac
import io
import json
import struct
import tarfile
import time
import zipfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from amberclaw.security.dlp import (
    ExternalTransmissionConfirmationError,
    ExternalTransmissionGuard,
)
from amberclaw.security.memory_safety import SecureSecret, zero_memory
from amberclaw.security.mfa import HardwareMFAManager, MFASecurityError
from amberclaw.security.mtls import (
    MTLSConfig,
    create_client_ssl_context,
    create_server_ssl_context,
    generate_mtls_test_pki,
    verify_peer_identity,
)
from amberclaw.security.prompt_guard import (
    PolicyLock,
    PolicyLockEngine,
    PolicyLockViolationError,
)
from amberclaw.security.retention import (
    DataRetentionManager,
    LegalHoldActiveError,
)
from amberclaw.security.sandbox import (
    DecompressionGuard,
    DecompressionSecurityError,
    EphemeralFilesystemSandbox,
    HostSocketAndMetadataFilter,
    SandboxEscapeTestRunner,
)


# =====================================================================
# 1. Mutual TLS (mTLS) Tests
# =====================================================================
def test_mtls_pki_and_ssl_context_creation(tmp_path: Path):
    pki = generate_mtls_test_pki(tmp_path)
    assert pki["ca_cert"].exists()
    assert pki["server_cert"].exists()
    assert pki["client_cert"].exists()

    # Server SSL Context
    srv_cfg = MTLSConfig(
        ca_cert_path=pki["ca_cert"],
        cert_path=pki["server_cert"],
        key_path=pki["server_key"],
        verify_peer=True,
    )
    srv_ctx = create_server_ssl_context(srv_cfg)
    assert srv_ctx.verify_mode.name == "CERT_REQUIRED"

    # Client SSL Context
    cli_cfg = MTLSConfig(
        ca_cert_path=pki["ca_cert"],
        cert_path=pki["client_cert"],
        key_path=pki["client_key"],
        verify_peer=True,
    )
    cli_ctx = create_client_ssl_context(cli_cfg)
    assert cli_ctx.verify_mode.name == "CERT_REQUIRED"

    # Peer identity verification
    mock_peer_cert = {
        "subject": ((("commonName", "amberclaw-gateway"),),),
        "subjectAltName": (("DNS", "localhost"), ("DNS", "amberclaw-gateway")),
    }
    assert verify_peer_identity(mock_peer_cert, ["amberclaw-gateway"])
    assert verify_peer_identity(mock_peer_cert, ["localhost"])
    assert not verify_peer_identity(mock_peer_cert, ["untrusted-attacker"])


# =====================================================================
# 2. Hardware MFA & FIDO2 / WebAuthn Tests
# =====================================================================
def test_fido2_assertion_and_replay_protection():
    manager = HardwareMFAManager()
    user_id = "admin_alice"
    cred_id = "cred_yubikey_01"
    rp_id = "amberclaw.local"

    # Generate test EC P-256 key
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )

    manager.register_fido2_key(user_id, cred_id, public_pem, rp_id)
    challenge = manager.generate_challenge()

    client_data_dict = {
        "type": "webauthn.get",
        "challenge": challenge,
        "origin": "https://amberclaw.local",
    }
    client_data_bytes = json.dumps(client_data_dict).encode("utf-8")
    client_data_hash = hashlib.sha256(client_data_bytes).digest()

    # Build authData: 32 bytes rpIdHash + 1 byte flags (0x05 = UP + UV) + 4 bytes sign_count (1)
    rp_id_hash = hashlib.sha256(rp_id.encode("utf-8")).digest()
    flags = b"\x05"
    sign_count = (1).to_bytes(4, byteorder="big")
    auth_data = rp_id_hash + flags + sign_count

    # Sign auth_data + client_data_hash
    signed_payload = auth_data + client_data_hash
    signature = private_key.sign(signed_payload, ec.ECDSA(hashes.SHA256()))

    # Verify assertion succeeds
    assert manager.verify_fido2_assertion(
        user_id=user_id,
        credential_id=cred_id,
        client_data_json=client_data_bytes,
        auth_data=auth_data,
        signature=signature,
        challenge=challenge,
    )

    # Replay with same challenge should fail (challenge already consumed)
    with pytest.raises(MFASecurityError, match="Challenge is invalid or has expired"):
        manager.verify_fido2_assertion(
            user_id=user_id,
            credential_id=cred_id,
            client_data_json=client_data_bytes,
            auth_data=auth_data,
            signature=signature,
            challenge=challenge,
        )

    # Attempt replay with rollback counter (count=1 when current is 1)
    new_challenge = manager.generate_challenge()
    client_data_dict["challenge"] = new_challenge
    client_data_bytes2 = json.dumps(client_data_dict).encode("utf-8")
    client_data_hash2 = hashlib.sha256(client_data_bytes2).digest()
    signed_payload2 = auth_data + client_data_hash2
    signature2 = private_key.sign(signed_payload2, ec.ECDSA(hashes.SHA256()))

    with pytest.raises(MFASecurityError, match="counter rollback"):
        manager.verify_fido2_assertion(
            user_id=user_id,
            credential_id=cred_id,
            client_data_json=client_data_bytes2,
            auth_data=auth_data,
            signature=signature2,
            challenge=new_challenge,
        )


def test_totp_verification_and_single_use():
    manager = HardwareMFAManager()
    user_id = "user_totp"
    # Base32 secret "MFRGGZDFMY======" -> b"hello!"
    secret = "MFRGGZDFMY======"
    manager.register_totp_secret(user_id, secret)

    # Compute expected current TOTP code manually
    key = base64.b32decode(secret, casefold=True)
    step = int(time.time()) // 30
    msg = struct.pack(">Q", step)
    h = py_hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code_int = struct.unpack(">I", h[offset : offset + 4])[0] & 0x7FFFFFFF
    valid_code = f"{code_int % 1_000_000:06d}"

    # First attempt succeeds
    assert manager.verify_totp(user_id, valid_code)
    # Replay attempt fails immediately
    assert not manager.verify_totp(user_id, valid_code)


# =====================================================================
# 3. Memory Safety & Sensitive Memory Zeroing Tests
# =====================================================================
def test_zero_memory():
    buf = bytearray(b"super_secret_master_key_12345678")
    assert any(b != 0 for b in buf)
    zero_memory(buf)
    assert all(b == 0 for b in buf)


def test_secure_secret_lifecycle():
    secret_text = "sk-ant-api03-ultra-secret-token"
    with SecureSecret(secret_text) as sec:
        assert not sec.is_wiped
        assert sec.get_str() == secret_text
        assert sec.compare(secret_text)
        assert str(sec) == "[REDACTED_SECURE_SECRET]"
        assert repr(sec).startswith("<SecureSecret status=active")

    # Outside context manager, buffer is wiped
    assert sec.is_wiped
    with pytest.raises(ValueError, match="Attempted to access wiped SecureSecret"):
        sec.get_bytes()
    assert not sec.compare(secret_text)


# =====================================================================
# 4. Sandbox Hardening & Decompression Guard Tests
# =====================================================================
def test_decompression_guard_zip_slip(tmp_path: Path):
    target_extract = tmp_path / "extract_dest"
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("../../etc/passwd", "root:x:0:0:root:/root:/bin/bash")

    with pytest.raises(DecompressionSecurityError, match="Zip-slip"):
        DecompressionGuard.extract_zip(zip_buffer.getvalue(), target_extract)


def test_decompression_guard_safe_zip(tmp_path: Path):
    target_extract = tmp_path / "safe_extract"
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("docs/readme.txt", "Safe contents")

    extracted = DecompressionGuard.extract_zip(zip_buffer.getvalue(), target_extract)
    assert len(extracted) == 1
    assert extracted[0].read_text() == "Safe contents"


def test_decompression_guard_tar_slip(tmp_path: Path):
    target_extract = tmp_path / "tar_dest"
    tar_buffer = io.BytesIO()

    with tarfile.open(fileobj=tar_buffer, mode="w") as tf:
        data = b"malicious content"
        ti = tarfile.TarInfo(name="../escape.txt")
        ti.size = len(data)
        tf.addfile(ti, io.BytesIO(data))

    with pytest.raises(DecompressionSecurityError, match="Tar-slip"):
        DecompressionGuard.extract_tar(tar_buffer.getvalue(), target_extract)


def test_host_socket_and_metadata_filter():
    # Socket paths
    assert HostSocketAndMetadataFilter.is_host_socket_path("/var/run/docker.sock")
    assert HostSocketAndMetadataFilter.is_host_socket_path("/var/run/containerd.sock")
    assert not HostSocketAndMetadataFilter.is_host_socket_path("/home/user/app.db")

    # Forbidden IP ranges
    assert HostSocketAndMetadataFilter.is_forbidden_ip("127.0.0.1")
    assert HostSocketAndMetadataFilter.is_forbidden_ip("169.254.169.254")
    assert HostSocketAndMetadataFilter.is_forbidden_ip("10.0.1.5")
    assert HostSocketAndMetadataFilter.is_forbidden_ip("192.168.1.1")
    assert HostSocketAndMetadataFilter.is_forbidden_ip("::1")
    assert not HostSocketAndMetadataFilter.is_forbidden_ip("8.8.8.8")

    # Redirect verification
    with pytest.raises(PermissionError, match="Prohibited redirect scheme"):
        HostSocketAndMetadataFilter.verify_redirect_url("gopher://127.0.0.1")

    with pytest.raises(PermissionError, match="Prohibited SSRF destination"):
        HostSocketAndMetadataFilter.verify_redirect_url(
            "http://169.254.169.254/latest/meta-data"
        )


def test_ephemeral_filesystem_sandbox():
    with EphemeralFilesystemSandbox() as sandbox:
        assert sandbox.path is not None
        assert sandbox.path.is_dir()

        safe_file = sandbox.resolve_safe_path("workspace/sub/test.txt")
        assert sandbox.path in safe_file.parents

        # Traversal attempt must be blocked
        with pytest.raises(PermissionError, match="Path traversal detected"):
            sandbox.resolve_safe_path("../../etc/shadow")

    # Directory was purged on exit
    assert not sandbox.path


@pytest.mark.asyncio
async def test_sandbox_escape_runner():
    runner = SandboxEscapeTestRunner()
    results = await runner.run_all_checks()
    assert results.get("host_socket_blocked") is True
    assert results.get("cloud_metadata_blocked") is True
    assert results.get("private_ip_blocked") is True


# =====================================================================
# 5. Policy Lock Engine Tests
# =====================================================================
def test_policy_lock_enforcement():
    lock = PolicyLock(
        tenant_id="tenant_alpha",
        session_id="session_xyz",
        allowed_tools=frozenset(["calculator", "read_file"]),
        denied_tools=frozenset(["shell", "exec_bash"]),
        allow_code_execution=False,
        allow_data_mutation=False,
    )

    # Allowed read tool passes
    assert PolicyLockEngine.enforce_tool_execution(
        lock=lock,
        tool_name="read_file",
        is_mutating=False,
        is_code_exec=False,
    )

    # Explicitly denied tool fails
    with pytest.raises(PolicyLockViolationError, match="blocked by policy lock"):
        PolicyLockEngine.enforce_tool_execution(
            lock=lock,
            tool_name="shell",
        )

    # Unlisted tool fails
    with pytest.raises(
        PolicyLockViolationError, match="not permitted under session policy lock"
    ):
        PolicyLockEngine.enforce_tool_execution(
            lock=lock,
            tool_name="write_file",
        )

    # Code execution blocked by policy
    with pytest.raises(PolicyLockViolationError, match="Code execution is prohibited"):
        PolicyLockEngine.enforce_tool_execution(
            lock=lock,
            tool_name="calculator",
            is_code_exec=True,
        )


# =====================================================================
# 6. External Transmission Guard Tests
# =====================================================================
def test_external_transmission_guard():
    clean_text = "General project status update: all tests passed."
    sensitive_text = (
        "Confidential customer SSN: 123-45-6789 and AWS key AKIAIOSFODNN7EXAMPLE"
    )

    # Clean text dispatches immediately
    assert (
        ExternalTransmissionGuard.check_transmission(
            content=clean_text,
            destination="https://api.external.com/webhook",
        )
        == clean_text
    )

    # Sensitive text without confirmation token raises ExternalTransmissionConfirmationError
    with pytest.raises(ExternalTransmissionConfirmationError) as exc_info:
        ExternalTransmissionGuard.check_transmission(
            content=sensitive_text,
            destination="https://api.external.com/webhook",
        )
    assert exc_info.value.destination == "https://api.external.com/webhook"
    assert "ssn" in exc_info.value.detected_patterns

    # Issue confirmation token and retry -> succeeds
    token = ExternalTransmissionGuard.issue_confirmation_token("confirm_send")
    dispatched = ExternalTransmissionGuard.check_transmission(
        content=sensitive_text,
        destination="https://api.external.com/webhook",
        confirmation_token=token,
    )
    assert dispatched == sensitive_text


# =====================================================================
# 7. Data Retention & Legal Hold Tests
# =====================================================================
def test_data_retention_ttl_and_legal_hold():
    manager = DataRetentionManager()
    user_id = "user_charlie"

    now = time.time()
    records = [
        {"id": 1, "timestamp": now - (10 * 86400), "text": "Recent 10 days ago"},
        {"id": 2, "timestamp": now - (40 * 86400), "text": "Expired 40 days ago"},
        {"id": 3, "timestamp": now - (60 * 86400), "text": "Expired 60 days ago"},
    ]

    # Without legal hold, 30-day TTL purges records 2 and 3
    retained, purged_count = manager.purge_expired_records(
        records=records,
        timestamp_field="timestamp",
        ttl_days=30,
    )
    assert purged_count == 2
    assert len(retained) == 1
    assert retained[0]["id"] == 1

    # Place legal hold on user
    manager.set_legal_hold("user", user_id, "Pending subpoena", "compliance_officer")
    assert manager.is_under_legal_hold("user", user_id)

    # When under legal hold, purge is blocked
    retained_held, purged_held = manager.purge_expired_records(
        records=records,
        ttl_days=30,
        entity_type="user",
        entity_id=user_id,
    )
    assert purged_held == 0
    assert len(retained_held) == 3

    # GDPR deletion must be blocked while under legal hold
    with pytest.raises(LegalHoldActiveError, match="active evidentiary legal hold"):
        manager.delete_user_data_compliance(user_id, [lambda uid: 5])

    # Export compliance archive works
    archive = manager.export_compliance_archive(user_id, {"chat_turns": records})
    assert archive["user_id"] == user_id
    assert "manifest_sha256" in archive
    assert "overall_integrity_sha256" in archive

    # Release legal hold
    assert manager.release_legal_hold("user", user_id, "compliance_officer")
    assert not manager.is_under_legal_hold("user", user_id)

    # Now GDPR deletion succeeds
    deleted = manager.delete_user_data_compliance(
        user_id, [lambda uid: 3, lambda uid: 2]
    )
    assert deleted == 5
