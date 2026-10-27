"""Unit tests for Hardware Enclave cryptography, attestation, and lifecycle management."""

import tempfile
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.exceptions import InvalidTag

from amberclaw.security.enclave.attestation import (
    AttestationVerifier,
    create_attestation_document,
)
from amberclaw.security.enclave.crypto import (
    EnclaveKeyAgreement,
    EnclaveSecureChannel,
    EnclaveSigner,
    compute_measurement_hash,
    generate_nonce,
    zeroize_buffer,
)
from amberclaw.security.enclave.diagnostics import get_enclave_diagnostics
from amberclaw.security.enclave.manager import EnclaveManager
from amberclaw.security.enclave.models import (
    EnclaveConfig,
    EnclaveMeasurement,
    EnclavePlatform,
    EnclaveStatus,
)


def test_key_agreement_ecdh() -> None:
    """Test ECDH X25519 key exchange between host and enclave parties."""
    host_party = EnclaveKeyAgreement()
    enclave_party = EnclaveKeyAgreement()

    # Host derives secret using enclave public key PEM
    host_secret = host_party.derive_shared_secret(enclave_party.public_key_pem)

    # Enclave derives secret using host public key PEM
    enclave_secret = enclave_party.derive_shared_secret(host_party.public_key_pem)

    assert len(host_secret) == 32  # noqa: PLR2004
    assert host_secret == enclave_secret


def test_secure_channel_aes_gcm() -> None:
    """Test AES-256-GCM encrypted channel across enclave boundary."""
    host_party = EnclaveKeyAgreement()
    enclave_party = EnclaveKeyAgreement()
    session_key = host_party.derive_shared_secret(enclave_party.public_key_pem)

    channel_host = EnclaveSecureChannel(session_key)
    channel_enclave = EnclaveSecureChannel(session_key)

    data = {"command": "execute_task", "secret_payload": "CLASSIFIED_MODEL_WEIGHTS"}
    encrypted = channel_host.encrypt_payload(data)
    assert isinstance(encrypted, str)
    assert "CLASSIFIED" not in encrypted

    decrypted = channel_enclave.decrypt_payload(encrypted)
    assert "CLASSIFIED_MODEL_WEIGHTS" in decrypted

    # Test tampering
    tampered = encrypted[:-4] + "AAAA"
    with pytest.raises((InvalidTag, ValueError)):
        channel_enclave.decrypt_payload(tampered)

    channel_host.close()
    channel_enclave.close()


def test_enclave_signer_signature_and_tampering() -> None:
    """Test ECDSA P-256 digital signature generation, verification, and tamper detection."""
    signer = EnclaveSigner()
    pubkey = signer.public_key_pem

    msg = "amberclaw-enclave-attestation-payload-v1"
    sig = signer.sign_message(msg)

    assert EnclaveSigner.verify_signature(pubkey, msg, sig) is True
    assert EnclaveSigner.verify_signature(pubkey, "tampered-message", sig) is False

    # Signer with different key
    other_signer = EnclaveSigner()
    assert EnclaveSigner.verify_signature(other_signer.public_key_pem, msg, sig) is False


def test_zeroize_buffer() -> None:
    """Test memory zeroization for sensitive key buffers."""
    buf = bytearray(b"super_secret_cryptographic_key_1234")
    assert any(b != 0 for b in buf)
    zeroize_buffer(buf)
    assert all(b == 0 for b in buf)


def test_attestation_verifier_positive_and_negative() -> None:
    """Test remote attestation verification, nonce checking, and measurement whitelist."""
    signer = EnclaveSigner()
    nonce = generate_nonce(32)
    pcr0 = compute_measurement_hash("kernel-image-v1", algorithm="sha384")
    measurements = EnclaveMeasurement(pcr0=pcr0, pcr1="runtime-hash", pcr2="app-hash")

    doc = create_attestation_document(
        platform=EnclavePlatform.NITRO,
        enclave_id="enclave-test-123",
        measurements=measurements,
        public_key_pem=EnclaveKeyAgreement().public_key_pem,
        nonce=nonce,
        signer=signer,
    )

    verifier = AttestationVerifier()

    # 1. Valid verification
    is_valid, msg = verifier.verify(
        doc=doc,
        expected_nonce=nonce,
        allowed_pcr0=[pcr0],
        platform_root_pubkey_pem=signer.public_key_pem,
    )
    assert is_valid is True
    assert "successfully" in msg

    # 2. Nonce mismatch
    is_valid_nonce, msg_nonce = verifier.verify(
        doc=doc,
        expected_nonce="wrong-nonce",
        platform_root_pubkey_pem=signer.public_key_pem,
    )
    assert is_valid_nonce is False
    assert "Nonce mismatch" in msg_nonce

    # 3. PCR0 measurement not in whitelist
    is_valid_pcr, msg_pcr = verifier.verify(
        doc=doc,
        expected_nonce=nonce,
        allowed_pcr0=["other-pcr0-hash"],
        platform_root_pubkey_pem=signer.public_key_pem,
    )
    assert is_valid_pcr is False
    assert "Untrusted enclave measurement PCR0" in msg_pcr

    # 4. Expired timestamp
    doc_expired = doc.model_copy(
        update={"timestamp_utc": (datetime.now(UTC) - timedelta(seconds=400)).isoformat()}
    )
    is_valid_exp, msg_exp = verifier.verify(
        doc=doc_expired,
        expected_nonce=nonce,
        max_age_seconds=300,
        platform_root_pubkey_pem=signer.public_key_pem,
    )
    assert is_valid_exp is False
    assert "expired" in msg_exp


def test_enclave_diagnostics() -> None:
    """Test gathering enclave hardware diagnostics."""
    diag = get_enclave_diagnostics()
    assert "simulated_enclave_available" in diag
    assert diag["simulated_enclave_available"] is True
    assert "platforms" in diag
    assert "nitro" in diag["platforms"]
    assert "sgx" in diag["platforms"]
    assert "sev_snp" in diag["platforms"]


@pytest.mark.asyncio
async def test_enclave_manager_lifecycle_and_execution() -> None:
    """Test EnclaveManager lifecycle: start, attestation, encrypted execution, and stop."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = EnclaveConfig(
            platform=EnclavePlatform.SIMULATED,
            memory_mb=256,
            vcpu_count=2,
            strict_attestation=True,
        )
        manager = EnclaveManager(config=config, workspace_dir=tmpdir)

        # Start and attest
        attestation = await manager.start()
        assert attestation is not None
        assert manager.is_ready is True
        assert manager.status == EnclaveStatus.READY

        # Execute Python inside enclave
        res_py = await manager.execute(
            command_type="python",
            payload="print('hello from attested enclave')",
        )
        assert res_py.exit_code == 0
        assert "hello from attested enclave" in res_py.stdout
        assert len(res_py.sealed_token) > 0

        # Execute Bash inside enclave
        res_bash = await manager.execute(
            command_type="bash",
            payload="echo 'bash inside enclave'",
        )
        assert res_bash.exit_code == 0
        assert "bash inside enclave" in res_bash.stdout

        # Stop enclave
        await manager.stop()
        assert manager.status == EnclaveStatus.TERMINATED


@pytest.mark.asyncio
async def test_enclave_manager_context_manager() -> None:
    """Test EnclaveManager async context manager support."""
    with tempfile.TemporaryDirectory() as tmpdir:
        async with EnclaveManager(workspace_dir=tmpdir) as enclave:
            assert enclave.is_ready is True
            res = await enclave.execute("python", "import sys; print(sys.version_info.major)")
            assert res.exit_code == 0
            assert "3" in res.stdout.strip()

        assert enclave.status == EnclaveStatus.TERMINATED
