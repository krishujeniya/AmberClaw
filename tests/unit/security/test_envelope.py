# ruff: noqa: S105
"""Unit tests for Envelope Encryption and Key Versioning.

Validates:
1. Two-tier KEK/DEK encryption and decryption roundtrip
2. Multi-version KEK rotation and active key promotion
3. Backwards-compatible decryption of historical envelopes
4. Cryptographic envelope re-wrapping without plaintext exposure
5. Missing key version handling and error boundaries
"""

from pathlib import Path

import pytest

from amberclaw.security.envelope import (
    EnvelopeEncryptionManager,
    EnvelopePayload,
)


def test_envelope_encryption_roundtrip(tmp_path: Path):
    manager = EnvelopeEncryptionManager(key_store_path=tmp_path)
    secret_text = "sk-super-secret-production-token-12345"

    envelope = manager.encrypt(secret_text, metadata={"service": "payment"})

    assert envelope.kek_version == "v1"
    assert envelope.encrypted_dek != ""
    assert envelope.ciphertext != ""
    assert envelope.metadata == {"service": "payment"}

    # Decrypt
    decrypted = manager.decrypt(envelope)
    assert decrypted == secret_text


def test_kek_rotation_and_historical_decryption(tmp_path: Path):
    manager = EnvelopeEncryptionManager(key_store_path=tmp_path)

    # 1. Encrypt under v1
    v1_envelope = manager.encrypt("data_encrypted_under_v1")
    assert v1_envelope.kek_version == "v1"

    # 2. Rotate KEK to v2
    new_version = manager.rotate_kek()
    assert new_version == "v2"
    assert manager.active_version == "v2"

    # 3. Encrypt new data under v2
    v2_envelope = manager.encrypt("data_encrypted_under_v2")
    assert v2_envelope.kek_version == "v2"

    # 4. Verify historical v1 envelope still decrypts seamlessly
    assert manager.decrypt(v1_envelope) == "data_encrypted_under_v1"
    # 5. Verify v2 envelope decrypts seamlessly
    assert manager.decrypt(v2_envelope) == "data_encrypted_under_v2"


def test_envelope_rewrap(tmp_path: Path):
    manager = EnvelopeEncryptionManager(key_store_path=tmp_path)

    # Encrypt under v1
    v1_envelope = manager.encrypt(
        "confidential_database_url", metadata={"db": "postgres"}
    )
    assert v1_envelope.kek_version == "v1"

    # Rotate to v2
    manager.rotate_kek()
    assert manager.active_version == "v2"

    # Re-wrap envelope to v2
    v2_envelope = manager.re_wrap(v1_envelope)
    assert v2_envelope.kek_version == "v2"
    assert v2_envelope.metadata == {"db": "postgres"}

    # Ciphertext changed due to new DEK and KEK
    assert v2_envelope.ciphertext != v1_envelope.ciphertext
    assert manager.decrypt(v2_envelope) == "confidential_database_url"


def test_missing_kek_version_raises(tmp_path: Path):
    manager = EnvelopeEncryptionManager(key_store_path=tmp_path)
    fake_envelope = EnvelopePayload(
        kek_version="v999_nonexistent",
        encrypted_dek="fake_dek",
        ciphertext="fake_cipher",
    )

    with pytest.raises(ValueError) as exc_info:
        manager.decrypt(fake_envelope)

    assert "KEK version 'v999_nonexistent' not found" in str(exc_info.value)
