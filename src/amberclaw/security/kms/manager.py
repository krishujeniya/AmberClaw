"""High-level KMS Secret Manager for Envelope Encryption and Key Rotation."""

import base64
import json
import os
import time
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from loguru import logger

from amberclaw.security.enclave.crypto import zeroize_buffer
from amberclaw.security.kms.models import EncryptedDataEnvelope, KMSConfig
from amberclaw.security.kms.provider import BaseKMSProvider, get_kms_provider

AES_GCM_NONCE_BYTES = 12


class KMSSecretManager:
    """Manages secret lifecycle with envelope encryption and KMS key rotation."""

    def __init__(
        self,
        config: KMSConfig | None = None,
        provider: BaseKMSProvider | None = None,
    ) -> None:
        self.config = config or KMSConfig()
        self.provider = provider or get_kms_provider(self.config)
        self._dek_cache: dict[str, tuple[bytes, float]] = {}

    async def encrypt_secret(
        self,
        secret_value: str | dict[str, Any],
        key_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EncryptedDataEnvelope:
        """Encrypt secret value using envelope encryption."""
        target_key_id = key_id or self.config.key_id
        meta = metadata or {}

        # 1. Obtain DEK from KMS
        plaintext_dek, encrypted_dek = await self.provider.generate_data_key(target_key_id)

        # 2. Serialize payload
        payload_str = json.dumps(secret_value) if isinstance(secret_value, dict) else str(secret_value)
        payload_bytes = payload_str.encode("utf-8")

        # 3. Encrypt payload with AES-256-GCM using plaintext DEK
        nonce = os.urandom(AES_GCM_NONCE_BYTES)
        aad = json.dumps(meta, sort_keys=True).encode("utf-8") if meta else b""
        aesgcm = AESGCM(plaintext_dek)
        ciphertext_and_tag = aesgcm.encrypt(nonce, payload_bytes, aad or None)

        # GCM tag is the last 16 bytes
        ciphertext = ciphertext_and_tag[:-16]
        tag = ciphertext_and_tag[-16:]

        # 4. Zeroize plaintext DEK
        dek_view = bytearray(plaintext_dek)
        zeroize_buffer(dek_view)

        return EncryptedDataEnvelope(
            provider=self.config.provider,
            key_id=target_key_id,
            encrypted_dek_b64=base64.b64encode(encrypted_dek).decode("utf-8"),
            iv_b64=base64.b64encode(nonce).decode("utf-8"),
            ciphertext_b64=base64.b64encode(ciphertext).decode("utf-8"),
            tag_b64=base64.b64encode(tag).decode("utf-8"),
            metadata=meta,
        )

    async def decrypt_secret(self, envelope: EncryptedDataEnvelope) -> str:
        """Decrypt secret envelope using KMS to unwrap the DEK."""
        encrypted_dek = base64.b64decode(envelope.encrypted_dek_b64)
        nonce = base64.b64decode(envelope.iv_b64)
        ciphertext = base64.b64decode(envelope.ciphertext_b64)
        tag = base64.b64decode(envelope.tag_b64)

        # Check DEK cache
        cache_key = envelope.encrypted_dek_b64
        now = time.time()
        plaintext_dek: bytes | None = None
        if cache_key in self._dek_cache:
            cached_dek, expiry = self._dek_cache[cache_key]
            if now < expiry:
                plaintext_dek = cached_dek

        if plaintext_dek is None:
            plaintext_dek = await self.provider.decrypt_data_key(envelope.key_id, encrypted_dek)
            if self.config.dek_cache_ttl_sec > 0:
                self._dek_cache[cache_key] = (plaintext_dek, now + self.config.dek_cache_ttl_sec)

        # Recombine ciphertext and tag for AESGCM
        ciphertext_and_tag = ciphertext + tag
        aad = json.dumps(envelope.metadata, sort_keys=True).encode("utf-8") if envelope.metadata else b""

        aesgcm = AESGCM(plaintext_dek)
        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext_and_tag, aad or None)
        return decrypted_bytes.decode("utf-8")

    async def rotate_key(
        self,
        envelope: EncryptedDataEnvelope,
        new_key_id: str,
    ) -> EncryptedDataEnvelope:
        """Decrypt secret with current key and re-encrypt under new Master Key."""
        plaintext = await self.decrypt_secret(envelope)
        logger.info("Rotating secret envelope from key '{}' to '{}'", envelope.key_id, new_key_id)
        return await self.encrypt_secret(plaintext, key_id=new_key_id, metadata=envelope.metadata)
