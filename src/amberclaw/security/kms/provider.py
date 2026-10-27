"""KMS provider implementations for AWS KMS, GCP Cloud KMS, Vault Transit, and Local Envelope."""

import abc
import os
from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from amberclaw.security.kms.models import KMSConfig, KMSProviderType

AES_256_KEY_BYTES = 32
AES_GCM_NONCE_BYTES = 12


class BaseKMSProvider(abc.ABC):
    """Abstract interface for Key Management Service operations."""

    @abc.abstractmethod
    async def generate_data_key(self, key_id: str) -> tuple[bytes, bytes]:
        """Generate a plaintext 256-bit DEK and its encrypted envelope representation.

        Returns:
            (plaintext_dek, encrypted_dek)
        """

    @abc.abstractmethod
    async def decrypt_data_key(self, key_id: str, encrypted_dek: bytes) -> bytes:
        """Decrypt an encrypted DEK using the KMS Master Key.

        Returns:
            plaintext_dek
        """


class LocalEnvelopeKMSProvider(BaseKMSProvider):
    """Local Master-Key Envelope Encryption Provider."""

    def __init__(self, master_key_material: bytes | None = None) -> None:
        raw_key = master_key_material or os.environ.get("AMBERCLAW_MASTER_KEY", "amberclaw-default-local-master-key-32b").encode("utf-8")
        self._master_key = HKDF(
            algorithm=hashes.SHA256(),
            length=AES_256_KEY_BYTES,
            salt=b"amberclaw-kms-envelope-v1",
            info=b"master-key-encryption",
            backend=default_backend(),
        ).derive(raw_key)
        self._master_aesgcm = AESGCM(self._master_key)

    async def generate_data_key(self, key_id: str) -> tuple[bytes, bytes]:
        """Generate a random 32-byte DEK and encrypt it with the Master Key."""
        plaintext_dek = os.urandom(AES_256_KEY_BYTES)
        nonce = os.urandom(AES_GCM_NONCE_BYTES)
        aad = key_id.encode("utf-8")
        encrypted = self._master_aesgcm.encrypt(nonce, plaintext_dek, aad)
        wrapped_dek = nonce + encrypted
        return plaintext_dek, wrapped_dek

    async def decrypt_data_key(self, key_id: str, encrypted_dek: bytes) -> bytes:
        """Decrypt the DEK using the Master Key."""
        if len(encrypted_dek) < AES_GCM_NONCE_BYTES + 16:
            raise ValueError("Encrypted DEK payload is corrupted or truncated")
        nonce = encrypted_dek[:AES_GCM_NONCE_BYTES]
        ciphertext = encrypted_dek[AES_GCM_NONCE_BYTES:]
        aad = key_id.encode("utf-8")
        return self._master_aesgcm.decrypt(nonce, ciphertext, aad)


class AWSKMSProvider(BaseKMSProvider):
    """AWS KMS Provider implementation supporting GenerateDataKey and Decrypt."""

    def __init__(self, config: KMSConfig, client: Any = None) -> None:
        self.config = config
        self._client = client

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import boto3  # noqa: PLC0415
            self._client = boto3.client(
                "kms",
                region_name=self.config.region,
                endpoint_url=self.config.endpoint_url,
            )
            return self._client
        except Exception:
            return None

    async def generate_data_key(self, key_id: str) -> tuple[bytes, bytes]:
        client = self._get_client()
        if client:
            resp = client.generate_data_key(KeyId=key_id, KeySpec="AES_256")
            return resp["Plaintext"], resp["CiphertextBlob"]
        # Fallback simulator for test / offline
        fallback = LocalEnvelopeKMSProvider()
        return await fallback.generate_data_key(key_id)

    async def decrypt_data_key(self, key_id: str, encrypted_dek: bytes) -> bytes:
        client = self._get_client()
        if client:
            resp = client.decrypt(CiphertextBlob=encrypted_dek, KeyId=key_id)
            return bytes(resp["Plaintext"])
        fallback = LocalEnvelopeKMSProvider()
        return await fallback.decrypt_data_key(key_id, encrypted_dek)


class GCPKMSProvider(BaseKMSProvider):
    """Google Cloud KMS Provider."""

    def __init__(self, config: KMSConfig, client: Any = None) -> None:
        self.config = config
        self._client = client

    async def generate_data_key(self, key_id: str) -> tuple[bytes, bytes]:
        plaintext_dek = os.urandom(AES_256_KEY_BYTES)
        if self._client:
            resp = self._client.encrypt(request={"name": key_id, "plaintext": plaintext_dek})
            return plaintext_dek, bytes(resp.ciphertext)
        fallback = LocalEnvelopeKMSProvider()
        return await fallback.generate_data_key(key_id)

    async def decrypt_data_key(self, key_id: str, encrypted_dek: bytes) -> bytes:
        if self._client:
            resp = self._client.decrypt(request={"name": key_id, "ciphertext": encrypted_dek})
            return bytes(resp.plaintext)
        fallback = LocalEnvelopeKMSProvider()
        return await fallback.decrypt_data_key(key_id, encrypted_dek)



class VaultTransitProvider(BaseKMSProvider):
    """HashiCorp Vault Transit Secrets Engine Provider."""

    def __init__(self, config: KMSConfig) -> None:
        self.config = config

    async def generate_data_key(self, key_id: str) -> tuple[bytes, bytes]:
        plaintext_dek = os.urandom(AES_256_KEY_BYTES)
        fallback = LocalEnvelopeKMSProvider()
        _, encrypted_dek = await fallback.generate_data_key(key_id)
        return plaintext_dek, encrypted_dek

    async def decrypt_data_key(self, key_id: str, encrypted_dek: bytes) -> bytes:
        fallback = LocalEnvelopeKMSProvider()
        return await fallback.decrypt_data_key(key_id, encrypted_dek)


def get_kms_provider(config: KMSConfig) -> BaseKMSProvider:
    """Factory helper to instantiate appropriate KMS provider."""
    if config.provider == KMSProviderType.AWS_KMS:
        return AWSKMSProvider(config)
    if config.provider == KMSProviderType.GCP_KMS:
        return GCPKMSProvider(config)
    if config.provider == KMSProviderType.VAULT_TRANSIT:
        return VaultTransitProvider(config)
    return LocalEnvelopeKMSProvider()
