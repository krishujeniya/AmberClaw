"""Unit tests for Cloud KMS, Envelope Encryption, and Secret Key Rotation."""

import pytest

from amberclaw.security.kms.manager import KMSSecretManager
from amberclaw.security.kms.models import KMSConfig, KMSProviderType
from amberclaw.security.kms.provider import (
    LocalEnvelopeKMSProvider,
    get_kms_provider,
)
from amberclaw.security.vault import SecretVault


@pytest.mark.asyncio
async def test_local_envelope_provider() -> None:
    """Test LocalEnvelopeKMSProvider DEK generation and unwrapping."""
    provider = LocalEnvelopeKMSProvider()
    key_id = "amberclaw-master-test-key"

    plaintext_dek, encrypted_dek = await provider.generate_data_key(key_id)
    assert len(plaintext_dek) == 32  # noqa: PLR2004
    assert len(encrypted_dek) > 32  # noqa: PLR2004
    assert plaintext_dek != encrypted_dek

    decrypted_dek = await provider.decrypt_data_key(key_id, encrypted_dek)
    assert decrypted_dek == plaintext_dek


@pytest.mark.asyncio
async def test_kms_secret_manager_envelope_encryption() -> None:
    """Test KMSSecretManager full encryption, decryption, and AAD verification."""
    config = KMSConfig(provider=KMSProviderType.LOCAL_ENVELOPE, key_id="key-primary-1")
    manager = KMSSecretManager(config=config)

    secret = "sk-live-amberclaw-super-secret-api-key-9999"  # noqa: S105
    metadata = {"app": "amberclaw", "env": "prod", "tenant": "enterprise-corp"}

    envelope = await manager.encrypt_secret(secret, metadata=metadata)
    assert envelope.key_id == "key-primary-1"
    assert envelope.provider == KMSProviderType.LOCAL_ENVELOPE
    assert secret not in envelope.ciphertext_b64

    decrypted = await manager.decrypt_secret(envelope)
    assert decrypted == secret


@pytest.mark.asyncio
async def test_kms_secret_manager_key_rotation() -> None:
    """Test rotating an encrypted secret envelope from one master key to another."""
    manager = KMSSecretManager(config=KMSConfig(key_id="old-master-key"))

    secret = "database-password-prod-12345"  # noqa: S105
    envelope_old = await manager.encrypt_secret(secret, key_id="old-master-key")
    assert envelope_old.key_id == "old-master-key"

    envelope_new = await manager.rotate_key(envelope_old, new_key_id="new-master-key-2026")
    assert envelope_new.key_id == "new-master-key-2026"

    # Decrypt rotated envelope
    decrypted = await manager.decrypt_secret(envelope_new)
    assert decrypted == secret


@pytest.mark.asyncio
async def test_kms_secret_manager_dek_cache() -> None:
    """Test that KMSSecretManager caches DEKs in memory within TTL."""
    config = KMSConfig(dek_cache_ttl_sec=60)
    manager = KMSSecretManager(config=config)

    secret = "cached-secret-value"  # noqa: S105
    envelope = await manager.encrypt_secret(secret)

    # First decrypt populates cache
    decrypted1 = await manager.decrypt_secret(envelope)
    assert decrypted1 == secret
    assert envelope.encrypted_dek_b64 in manager._dek_cache

    # Second decrypt uses cached DEK
    decrypted2 = await manager.decrypt_secret(envelope)
    assert decrypted2 == secret


def test_vault_kms_integration() -> None:
    """Test SecretVault configured with KMS support."""
    config = KMSConfig(key_id="vault-kms-key")
    vault_inst = SecretVault(key_dir=None, kms_config=config)
    assert vault_inst.kms_manager is not None
    assert vault_inst.kms_manager.config.key_id == "vault-kms-key"


def test_get_kms_provider_factory() -> None:
    """Test KMS provider factory instantiations."""
    aws_prov = get_kms_provider(KMSConfig(provider=KMSProviderType.AWS_KMS))
    assert aws_prov.__class__.__name__ == "AWSKMSProvider"

    gcp_prov = get_kms_provider(KMSConfig(provider=KMSProviderType.GCP_KMS))
    assert gcp_prov.__class__.__name__ == "GCPKMSProvider"

    vault_prov = get_kms_provider(KMSConfig(provider=KMSProviderType.VAULT_TRANSIT))
    assert vault_prov.__class__.__name__ == "VaultTransitProvider"

    local_prov = get_kms_provider(KMSConfig(provider=KMSProviderType.LOCAL_ENVELOPE))
    assert local_prov.__class__.__name__ == "LocalEnvelopeKMSProvider"
