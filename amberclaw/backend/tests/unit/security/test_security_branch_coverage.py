"""Comprehensive branch coverage tests for security modules.

Covers landlock, isolation, memory_safety, envelope, kms, mfa, and sandbox
edge cases and defensive boundaries.
"""

from __future__ import annotations

import ctypes
import hashlib
import io
import json
import os
import socket
import sys
import tarfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

from amberclaw.security.envelope import EnvelopeEncryptionManager, EnvelopePayload
from amberclaw.security.isolation import (
    ProcessIsolationConfig,
    ResourceLimits,
    apply_resource_limits,
    get_preexec_isolation_fn,
)
from amberclaw.security.kms.models import KMSConfig, KMSProviderType
from amberclaw.security.kms.provider import (
    AWSKMSProvider,
    GCPKMSProvider,
    LocalEnvelopeKMSProvider,
    VaultTransitProvider,
    get_kms_provider,
)
from amberclaw.security.landlock import _add_path_rule, apply_sandbox
from amberclaw.security.memory_safety import SecureSecret, zero_memory
from amberclaw.security.mfa import HardwareMFAManager, MFASecurityError
from amberclaw.security.sandbox import (
    DecompressionGuard,
    DecompressionSecurityError,
    HostSocketAndMetadataFilter,
    apply_seccomp_filters,
)

# ==============================================================================
# Landlock Tests
# ==============================================================================


def test_landlock_apply_sandbox_non_linux(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("amberclaw.security.landlock.IS_LINUX", False)
    assert apply_sandbox(str(tmp_path)) is False


def test_landlock_apply_sandbox_cdll_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("amberclaw.security.landlock.IS_LINUX", True)
    monkeypatch.setattr(ctypes, "CDLL", MagicMock(side_effect=RuntimeError("no libc")))
    assert apply_sandbox(str(tmp_path)) is False


def test_landlock_apply_sandbox_ruleset_create_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("amberclaw.security.landlock.IS_LINUX", True)
    mock_libc = MagicMock()
    mock_libc.syscall.return_value = -1
    monkeypatch.setattr(ctypes, "CDLL", MagicMock(return_value=mock_libc))
    assert apply_sandbox(str(tmp_path)) is False


def test_landlock_apply_sandbox_restrict_self_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("amberclaw.security.landlock.IS_LINUX", True)
    mock_libc = MagicMock()
    mock_libc.syscall.side_effect = [10, -1]  # ruleset_fd=10, restrict_self=-1
    mock_libc.prctl.return_value = 0
    monkeypatch.setattr(ctypes, "CDLL", MagicMock(return_value=mock_libc))
    monkeypatch.setattr(os, "close", MagicMock())
    assert apply_sandbox(str(tmp_path)) is False


def test_landlock_apply_sandbox_prctl_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("amberclaw.security.landlock.IS_LINUX", True)
    mock_libc = MagicMock()
    mock_libc.syscall.return_value = 10
    mock_libc.prctl.return_value = -1
    monkeypatch.setattr(ctypes, "CDLL", MagicMock(return_value=mock_libc))
    monkeypatch.setattr(os, "close", MagicMock())
    assert apply_sandbox(str(tmp_path)) is False


def test_landlock_apply_sandbox_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("amberclaw.security.landlock.IS_LINUX", True)
    ruleset_create_syscall = 444

    def mock_syscall(sys_no: int, *_: object) -> int:
        return 10 if sys_no == ruleset_create_syscall else 0

    mock_libc = MagicMock()
    mock_libc.syscall.side_effect = mock_syscall
    mock_libc.prctl.return_value = 0
    monkeypatch.setattr(ctypes, "CDLL", MagicMock(return_value=mock_libc))
    monkeypatch.setattr(os, "close", MagicMock())
    assert apply_sandbox(str(tmp_path)) is True


def test_landlock_add_path_rule_open_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(os, "open", MagicMock(side_effect=OSError("open failed")))
    mock_libc = MagicMock()
    _add_path_rule(mock_libc, 10, "/nonexistent/path", 1)
    mock_libc.syscall.assert_not_called()


def test_landlock_add_path_rule_syscall_exception(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(os, "open", MagicMock(return_value=5))
    monkeypatch.setattr(os, "close", MagicMock())
    mock_libc = MagicMock()
    mock_libc.syscall.side_effect = RuntimeError("syscall failed")
    _add_path_rule(mock_libc, 10, str(tmp_path), 1)
    os.close.assert_called_with(5)


# ==============================================================================
# Isolation Tests
# ==============================================================================


def test_isolation_apply_resource_limits_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    # Should safely return without error on Windows
    apply_resource_limits(ResourceLimits())


def test_isolation_apply_resource_limits_posix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_resource = MagicMock()
    mock_resource.RLIMIT_AS = 9
    mock_resource.RLIMIT_CPU = 0
    mock_resource.RLIMIT_NOFILE = 7
    mock_resource.RLIMIT_NPROC = 6
    monkeypatch.setattr("amberclaw.security.isolation.resource", mock_resource)
    monkeypatch.setattr(sys, "platform", "linux")

    expected_limit_calls = 4
    limits = ResourceLimits(
        max_memory_bytes=1048576,
        max_cpu_seconds=5,
        max_open_files=32,
        max_processes=8,
    )
    apply_resource_limits(limits)
    assert mock_resource.setrlimit.call_count == expected_limit_calls


def test_isolation_apply_resource_limits_suppresses_oserror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_resource = MagicMock()
    mock_resource.setrlimit.side_effect = OSError("Operation not permitted")
    monkeypatch.setattr("amberclaw.security.isolation.resource", mock_resource)
    monkeypatch.setattr(sys, "platform", "linux")
    # Must suppress OSError cleanly
    apply_resource_limits(ResourceLimits())


def test_isolation_get_preexec_isolation_fn_disabled() -> None:
    cfg = ProcessIsolationConfig(enabled=False)
    assert get_preexec_isolation_fn(cfg) is None


def test_isolation_get_preexec_isolation_fn_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    cfg = ProcessIsolationConfig(enabled=True)
    assert get_preexec_isolation_fn(cfg) is None


def test_isolation_get_preexec_isolation_fn_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    cfg = ProcessIsolationConfig(enabled=True)
    fn = get_preexec_isolation_fn(cfg)
    assert callable(fn)
    with patch("amberclaw.security.isolation.apply_resource_limits") as mock_apply:
        fn()
        mock_apply.assert_called_once_with(cfg.limits)


# ==============================================================================
# Memory Safety Tests
# ==============================================================================


def test_zero_memory_none_and_empty() -> None:
    zero_memory(None)
    empty = bytearray()
    zero_memory(empty)
    assert len(empty) == 0


def test_zero_memory_memoryview_writable_and_readonly() -> None:
    buf = bytearray(b"secret123")
    mv = memoryview(buf)
    zero_memory(mv)
    assert bytes(buf) == b"\x00" * 9

    readonly_mv = memoryview(b"immutable")
    zero_memory(readonly_mv)  # must not raise on readonly


def test_zero_memory_ctypes_array() -> None:
    arr = (ctypes.c_char * 8)(*b"test1234")
    zero_memory(arr)
    assert bytes(arr) == b"\x00" * 8


def test_zero_memory_fallback_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buf = bytearray(b"fallback_secret")
    monkeypatch.setattr(
        ctypes, "memset", MagicMock(side_effect=RuntimeError("memset failed"))
    )
    zero_memory(buf)
    assert bytes(buf) == b"\x00" * len(b"fallback_secret")


def test_secure_secret_type_validation() -> None:
    with pytest.raises(TypeError, match="Unsupported secret type"):
        SecureSecret(12345)  # type: ignore[arg-type]

    sec_bytes = SecureSecret(b"raw-bytes")
    assert sec_bytes.get_bytes() == b"raw-bytes"

    sec_bytearray = SecureSecret(bytearray(b"from-bytearray"))
    assert sec_bytearray.get_str() == "from-bytearray"


def test_secure_secret_wiped_access_errors() -> None:
    sec = SecureSecret("secret-pass")
    sec.wipe()
    assert sec.is_wiped is True

    with pytest.raises(ValueError, match="Attempted to access wiped SecureSecret"):
        sec.get_bytes()

    with pytest.raises(ValueError, match="Attempted to access wiped SecureSecret"):
        sec.get_str()


def test_secure_secret_compare_permutations() -> None:
    sec1 = SecureSecret("match-target")
    sec2 = SecureSecret("match-target")
    sec3 = SecureSecret("mismatched")

    assert sec1.compare(sec2) is True
    assert sec1.compare(sec3) is False
    assert sec1.compare("match-target") is True
    assert sec1.compare("mismatched") is False
    assert sec1.compare(b"match-target") is True
    assert sec1.compare(bytearray(b"match-target")) is True
    assert sec1.compare(12345) is False  # type: ignore[arg-type]

    sec2.wipe()
    assert sec1.compare(sec2) is False

    sec1.wipe()
    assert sec1.compare("match-target") is False


# ==============================================================================
# Envelope Encryption Tests
# ==============================================================================


def test_envelope_manager_corrupted_keystore_recovery(
    tmp_path: Path,
) -> None:
    key_file = tmp_path / "keyrings.json"
    key_file.write_text("invalid json content!", encoding="utf-8")

    manager = EnvelopeEncryptionManager(key_store_path=tmp_path)
    assert manager.active_version == "v1"
    assert "v1" in manager._keks


def test_envelope_manager_rotate_kek_non_v_prefix(tmp_path: Path) -> None:
    manager = EnvelopeEncryptionManager(key_store_path=tmp_path)
    manager._active_version = "custom_1"
    new_v = manager.rotate_kek()
    assert new_v.startswith("v")


def test_envelope_manager_decrypt_unknown_version_raises(
    tmp_path: Path,
) -> None:
    manager = EnvelopeEncryptionManager(key_store_path=tmp_path)
    bad_env = EnvelopePayload(
        kek_version="v999",
        encrypted_dek="dGVzdA==",
        ciphertext="dGVzdA==",
    )
    with pytest.raises(ValueError, match="KEK version 'v999' not found"):
        manager.decrypt(bad_env)


def test_envelope_manager_rewrap_same_version_noop(tmp_path: Path) -> None:
    manager = EnvelopeEncryptionManager(key_store_path=tmp_path)
    env = manager.encrypt("payload")
    rewrapped = manager.re_wrap(env)
    assert rewrapped is env


# ==============================================================================
# KMS Provider Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_local_kms_corrupted_dek_payload() -> None:
    provider = LocalEnvelopeKMSProvider()
    with pytest.raises(
        ValueError, match="Encrypted DEK payload is corrupted or truncated"
    ):
        await provider.decrypt_data_key("key-1", b"short")


@pytest.mark.asyncio
async def test_aws_kms_provider_with_mock_client() -> None:
    mock_client = MagicMock()
    mock_client.generate_data_key.return_value = {
        "Plaintext": b"\x01" * 32,
        "CiphertextBlob": b"\x02" * 48,
    }
    mock_client.decrypt.return_value = {"Plaintext": b"\x01" * 32}

    cfg = KMSConfig(
        provider=KMSProviderType.AWS_KMS, region="us-east-1", key_id="arn:aws:kms"
    )
    provider = AWSKMSProvider(cfg, client=mock_client)

    pt, ct = await provider.generate_data_key("arn:aws:kms")
    assert pt == b"\x01" * 32
    assert ct == b"\x02" * 48

    decrypted = await provider.decrypt_data_key("arn:aws:kms", ct)
    assert decrypted == b"\x01" * 32


@pytest.mark.asyncio
async def test_aws_kms_provider_fallback_when_client_none() -> None:
    expected_key_bytes = 32
    cfg = KMSConfig(
        provider=KMSProviderType.AWS_KMS, region="us-east-1", key_id="key-1"
    )
    provider = AWSKMSProvider(cfg, client=None)
    provider._get_client = MagicMock(return_value=None)  # type: ignore[method-assign]

    pt, ct = await provider.generate_data_key("key-1")
    assert len(pt) == expected_key_bytes
    decrypted = await provider.decrypt_data_key("key-1", ct)
    assert decrypted == pt


@pytest.mark.asyncio
async def test_gcp_kms_provider_with_mock_client() -> None:
    expected_key_bytes = 32
    mock_client = MagicMock()
    mock_resp_enc = SimpleNamespace(ciphertext=b"\x03" * 48)
    mock_resp_dec = SimpleNamespace(plaintext=b"\x04" * 32)
    mock_client.encrypt.return_value = mock_resp_enc
    mock_client.decrypt.return_value = mock_resp_dec

    cfg = KMSConfig(provider=KMSProviderType.GCP_KMS, key_id="projects/kms")
    provider = GCPKMSProvider(cfg, client=mock_client)

    pt, ct = await provider.generate_data_key("projects/kms")
    assert len(pt) == expected_key_bytes
    assert ct == b"\x03" * 48

    decrypted = await provider.decrypt_data_key("projects/kms", ct)
    assert decrypted == b"\x04" * 32


@pytest.mark.asyncio
async def test_gcp_kms_provider_fallback_when_client_none() -> None:
    expected_key_bytes = 32
    cfg = KMSConfig(provider=KMSProviderType.GCP_KMS, key_id="projects/kms")
    provider = GCPKMSProvider(cfg, client=None)

    pt, ct = await provider.generate_data_key("projects/kms")
    assert len(pt) == expected_key_bytes
    decrypted = await provider.decrypt_data_key("projects/kms", ct)
    assert decrypted == pt


@pytest.mark.asyncio
async def test_vault_transit_provider() -> None:
    expected_key_bytes = 32
    cfg = KMSConfig(provider=KMSProviderType.VAULT_TRANSIT, key_id="transit/key")
    provider = VaultTransitProvider(cfg)

    pt, ct = await provider.generate_data_key("transit/key")
    assert len(pt) == expected_key_bytes
    decrypted = await provider.decrypt_data_key("transit/key", ct)
    assert decrypted == pt


def test_get_kms_provider_factory() -> None:
    assert isinstance(
        get_kms_provider(KMSConfig(provider=KMSProviderType.AWS_KMS)),
        AWSKMSProvider,
    )
    assert isinstance(
        get_kms_provider(KMSConfig(provider=KMSProviderType.GCP_KMS)),
        GCPKMSProvider,
    )
    assert isinstance(
        get_kms_provider(KMSConfig(provider=KMSProviderType.VAULT_TRANSIT)),
        VaultTransitProvider,
    )
    assert isinstance(
        get_kms_provider(KMSConfig(provider=KMSProviderType.LOCAL_ENVELOPE)),
        LocalEnvelopeKMSProvider,
    )


# ==============================================================================
# Hardware MFA & FIDO2 Validation Tests
# ==============================================================================


def test_mfa_register_invalid_pem() -> None:
    manager = HardwareMFAManager()
    with pytest.raises(MFASecurityError, match="Invalid public key PEM"):
        manager.register_fido2_key("user1", "cred1", "not-a-pem", "rp1")


def test_mfa_verify_invalid_or_expired_challenge() -> None:
    manager = HardwareMFAManager()
    with pytest.raises(MFASecurityError, match="Challenge is invalid"):
        manager.verify_fido2_assertion(
            user_id="u1",
            credential_id="c1",
            client_data_json="{}",
            auth_data=b"0" * 37,
            signature=b"sig",
            challenge="nonexistent-challenge",
        )


def test_mfa_verify_credential_not_found() -> None:
    manager = HardwareMFAManager()
    ch = manager.generate_challenge()
    with pytest.raises(MFASecurityError, match="Credential \\[c1\\] not found"):
        manager.verify_fido2_assertion(
            user_id="u1",
            credential_id="c1",
            client_data_json="{}",
            auth_data=b"0" * 37,
            signature=b"sig",
            challenge=ch,
        )


def test_mfa_verify_malformed_client_data_json() -> None:
    manager = HardwareMFAManager()
    key = ec.generate_private_key(ec.SECP256R1())
    pem = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    manager.register_fido2_key("u1", "c1", pem, "rp.local")
    ch = manager.generate_challenge()

    with pytest.raises(MFASecurityError, match="Malformed clientDataJSON"):
        manager.verify_fido2_assertion(
            user_id="u1",
            credential_id="c1",
            client_data_json="not-json",
            auth_data=b"0" * 37,
            signature=b"sig",
            challenge=ch,
        )


def test_mfa_verify_unexpected_client_data_type() -> None:
    manager = HardwareMFAManager()
    key = ec.generate_private_key(ec.SECP256R1())
    pem = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    manager.register_fido2_key("u1", "c1", pem, "rp.local")
    ch = manager.generate_challenge()
    client_data = json.dumps({"type": "webauthn.create", "challenge": ch})

    with pytest.raises(MFASecurityError, match="Unexpected clientData type"):
        manager.verify_fido2_assertion(
            user_id="u1",
            credential_id="c1",
            client_data_json=client_data,
            auth_data=b"0" * 37,
            signature=b"sig",
            challenge=ch,
        )


def test_mfa_verify_challenge_mismatch() -> None:
    manager = HardwareMFAManager()
    key = ec.generate_private_key(ec.SECP256R1())
    pem = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    manager.register_fido2_key("u1", "c1", pem, "rp.local")
    ch = manager.generate_challenge()
    client_data = json.dumps({"type": "webauthn.get", "challenge": "different"})

    with pytest.raises(MFASecurityError, match="ClientData challenge does not match"):
        manager.verify_fido2_assertion(
            user_id="u1",
            credential_id="c1",
            client_data_json=client_data,
            auth_data=b"0" * 37,
            signature=b"sig",
            challenge=ch,
        )


def test_mfa_verify_auth_data_short_and_rp_mismatch() -> None:
    manager = HardwareMFAManager()
    key = ec.generate_private_key(ec.SECP256R1())
    pem = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    manager.register_fido2_key("u1", "c1", pem, "rp.local")

    ch = manager.generate_challenge()
    client_data = json.dumps({"type": "webauthn.get", "challenge": ch})
    with pytest.raises(MFASecurityError, match="payload too short"):
        manager.verify_fido2_assertion(
            user_id="u1",
            credential_id="c1",
            client_data_json=client_data,
            auth_data=b"too_short",
            signature=b"sig",
            challenge=ch,
        )

    ch2 = manager.generate_challenge()
    client_data2 = json.dumps({"type": "webauthn.get", "challenge": ch2})
    wrong_rp_hash = b"\x00" * 32
    auth_data = wrong_rp_hash + b"\x01" + (1).to_bytes(4, "big")
    with pytest.raises(MFASecurityError, match="RP ID hash mismatch"):
        manager.verify_fido2_assertion(
            user_id="u1",
            credential_id="c1",
            client_data_json=client_data2,
            auth_data=auth_data,
            signature=b"sig",
            challenge=ch2,
        )


def test_mfa_verify_user_presence_missing() -> None:
    manager = HardwareMFAManager()
    key = ec.generate_private_key(ec.SECP256R1())
    pem = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    rp_id = "rp.local"
    manager.register_fido2_key("u1", "c1", pem, rp_id)

    ch = manager.generate_challenge()
    client_data = json.dumps({"type": "webauthn.get", "challenge": ch})
    rp_hash = hashlib.sha256(rp_id.encode()).digest()
    auth_data = rp_hash + b"\x00" + (1).to_bytes(4, "big")  # flag 0 = no UP
    with pytest.raises(
        MFASecurityError, match=r"User Presence \(UP\) flag was not set"
    ):
        manager.verify_fido2_assertion(
            user_id="u1",
            credential_id="c1",
            client_data_json=client_data,
            auth_data=auth_data,
            signature=b"sig",
            challenge=ch,
        )


def test_mfa_verify_rsa_key_assertion() -> None:
    manager = HardwareMFAManager()
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = (
        rsa_key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    rp_id = "rp.local"
    manager.register_fido2_key("u_rsa", "c_rsa", pem, rp_id)

    ch = manager.generate_challenge()
    client_data_bytes = json.dumps({"type": "webauthn.get", "challenge": ch}).encode()
    client_data_hash = hashlib.sha256(client_data_bytes).digest()

    rp_hash = hashlib.sha256(rp_id.encode()).digest()
    auth_data = rp_hash + b"\x01" + (1).to_bytes(4, "big")
    signed_payload = auth_data + client_data_hash
    signature = rsa_key.sign(signed_payload, padding.PKCS1v15(), hashes.SHA256())

    assert (
        manager.verify_fido2_assertion(
            user_id="u_rsa",
            credential_id="c_rsa",
            client_data_json=client_data_bytes,
            auth_data=auth_data,
            signature=signature,
            challenge=ch,
        )
        is True
    )


def test_mfa_verify_totp_negative_cases() -> None:
    manager = HardwareMFAManager()
    # Unregistered user raises MFASecurityError
    with pytest.raises(MFASecurityError, match="No TOTP secret enrolled"):
        manager.verify_totp("unknown_user", "123456")

    manager.register_totp_secret("u1", "MFRGGZDFMY======")
    # Invalid length or non-numeric
    assert manager.verify_totp("u1", "123") is False
    assert manager.verify_totp("u1", "abcdef") is False
    # Wrong code
    assert manager.verify_totp("u1", "000000") is False


# ==============================================================================
# Sandbox & Decompression Guard Tests
# ==============================================================================


def test_decompression_guard_zip_max_files(tmp_path: Path) -> None:
    zip_bytes = io.BytesIO()
    with zipfile.ZipFile(zip_bytes, "w") as zf:
        zf.writestr("file1.txt", "content1")
        zf.writestr("file2.txt", "content2")

    zip_bytes.seek(0)
    with pytest.raises(DecompressionSecurityError, match="exceeding limit of 1"):
        DecompressionGuard.extract_zip(zip_bytes, tmp_path / "out", max_files=1)


def test_decompression_guard_zip_max_bytes(tmp_path: Path) -> None:
    zip_bytes = io.BytesIO()
    with zipfile.ZipFile(zip_bytes, "w") as zf:
        zf.writestr("large.txt", "A" * 1000)

    zip_bytes.seek(0)
    with pytest.raises(
        DecompressionSecurityError, match="Decompressed size exceeds limit"
    ):
        DecompressionGuard.extract_zip(zip_bytes, tmp_path / "out", max_bytes=100)


def test_decompression_guard_zip_slip_traversal(tmp_path: Path) -> None:
    zip_bytes = io.BytesIO()
    with zipfile.ZipFile(zip_bytes, "w") as zf:
        zf.writestr("../../etc/passwd", "evil")

    zip_bytes.seek(0)
    with pytest.raises(
        DecompressionSecurityError, match="Zip-slip directory traversal"
    ):
        DecompressionGuard.extract_zip(zip_bytes, tmp_path / "out")


def test_decompression_guard_tar_slip_and_limits(tmp_path: Path) -> None:
    tar_bytes = io.BytesIO()
    with tarfile.open(fileobj=tar_bytes, mode="w") as tf:
        ti = tarfile.TarInfo(name="../../evil.txt")
        ti.size = 4
        tf.addfile(ti, io.BytesIO(b"evil"))

    tar_bytes.seek(0)
    with pytest.raises(
        DecompressionSecurityError, match="Tar-slip directory traversal"
    ):
        DecompressionGuard.extract_tar(tar_bytes, tmp_path / "tar_out")


def test_host_socket_and_metadata_filter() -> None:
    flt = HostSocketAndMetadataFilter
    # Forbidden IPs
    assert flt.is_forbidden_ip("127.0.0.1") is True
    assert flt.is_forbidden_ip("169.254.169.254") is True
    assert flt.is_forbidden_ip("10.1.2.3") is True
    assert flt.is_forbidden_ip("192.168.0.1") is True
    assert flt.is_forbidden_ip("8.8.8.8") is False
    assert flt.is_forbidden_ip("invalid-ip") is True

    # Forbidden Hostnames
    assert flt.verify_destination_host("metadata.google.internal") is False
    assert flt.verify_destination_host("instance-data") is False

    # DNS failure
    with patch("socket.getaddrinfo", side_effect=socket.gaierror):
        assert flt.verify_destination_host("unknown.domain.tld") is False

    # URL redirect validation
    with pytest.raises(PermissionError, match="Prohibited redirect scheme: ftp"):
        flt.verify_redirect_url("ftp://example.com/file")

    with pytest.raises(PermissionError, match="Redirect URL missing hostname"):
        flt.verify_redirect_url("http:///missing-host")

    # Socket path check
    assert flt.is_host_socket_path("/var/run/docker.sock") is True
    assert flt.is_host_socket_path("/run/containerd.sock") is True
    assert flt.is_host_socket_path("/var/amberclaw/safe.sock") is False


def test_apply_seccomp_filters_fallback() -> None:
    with (
        patch("platform.system", return_value="Darwin"),
        patch("ctypes.CDLL", side_effect=Exception("no ctypes")),
    ):
        assert apply_seccomp_filters() is False
