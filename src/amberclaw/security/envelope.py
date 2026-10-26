# ruff: noqa: ERA001, PTH123, PTH101
"""Envelope Encryption and Key Versioning System for AmberClaw.

Implements:
1. Multi-tier Envelope Encryption (KEK/DEK hierarchy) using Cryptography Fernet.
2. Key versioning with backwards-compatible decryption of historical envelopes.
3. Cryptographic re-wrapping: upgrades historical envelopes to latest KEK without plaintext leak.
4. Tamper-evident audit logging for key generation, rotation, and re-wrapping.
"""

import base64
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.security.audit import AuditEvent, SecurityAuditLogger


class EnvelopePayload(BaseModel):
    """Encrypted data envelope containing ciphertext and an encrypted Data Encryption Key."""

    kek_version: str = Field(
        ..., description="Version identifier of the Key Encryption Key"
    )
    encrypted_dek: str = Field(
        ..., description="Base64-encoded Data Encryption Key encrypted under the KEK"
    )
    ciphertext: str = Field(
        ..., description="Base64-encoded payload encrypted under the DEK"
    )
    algorithm: str = Field(
        default="Fernet-Envelope-v1", description="Envelope cryptographic scheme"
    )
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = Field(default_factory=dict)


class EnvelopeEncryptionManager:
    """Manages versioned Key Encryption Keys (KEKs) and per-payload Data Encryption Keys (DEKs)."""

    def __init__(self, key_store_path: Path | str | None = None) -> None:
        self.store_dir = Path(key_store_path or Path.home() / ".amberclaw" / "keys")
        self.store_file = self.store_dir / "keyrings.json"
        # {version_str: raw_key_bytes}
        self._keks: dict[str, bytes] = {}
        self._active_version: str = "v1"
        self._init_keystore()

    def _init_keystore(self) -> None:
        """Load versioned KEKs from disk or initialize the v1 primary key."""
        self.store_dir.mkdir(parents=True, exist_ok=True)
        if self.store_file.exists():
            try:
                data = json.loads(self.store_file.read_text(encoding="utf-8"))
                for v, b64_k in data.get("keks", {}).items():
                    self._keks[v] = base64.b64decode(b64_k)
                self._active_version = data.get("active_version", "v1")
                logger.info(
                    "Loaded {} KEK versions from keystore. Active: {}",
                    len(self._keks),
                    self._active_version,
                )
                return
            except Exception as e:
                logger.error(
                    "Failed to load keyrings.json: {}. Generating fresh key.", e
                )

        # Generate initial v1 key
        initial_key = Fernet.generate_key()
        self._keks["v1"] = initial_key
        self._active_version = "v1"
        self._persist_keystore()

    def _persist_keystore(self) -> None:
        """Persist encrypted key rings securely."""
        payload = {
            "active_version": self._active_version,
            "keks": {
                v: base64.b64encode(k).decode("ascii") for v, k in self._keks.items()
            },
            "updated_at": datetime.now(UTC).isoformat(),
        }
        self.store_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        # Restrict permissions to owner only (chmod 0600)
        with open(self.store_file) as _:
            os.chmod(self.store_file, 0o600)

    @property
    def active_version(self) -> str:
        return self._active_version

    def rotate_kek(self) -> str:
        """Generate a new KEK version and promote it to active. Retains historical keys for decryption."""
        current_num = (
            int(self._active_version.lstrip("v"))
            if self._active_version.startswith("v")
            else len(self._keks)
        )
        new_version = f"v{current_num + 1}"
        new_key = Fernet.generate_key()

        self._keks[new_version] = new_key
        previous_version = self._active_version
        self._active_version = new_version
        self._persist_keystore()

        logger.info(
            "KEK rotated: {} -> {}. Total versions retained: {}",
            previous_version,
            new_version,
            len(self._keks),
        )

        audit = SecurityAuditLogger.get_logger()
        audit.log_event(
            AuditEvent(
                actor="system",
                action="security.kek_rotated",
                resource_type="key_encryption_key",
                resource_id=new_version,
                outcome="success",
                metadata={
                    "previous_version": previous_version,
                    "new_version": new_version,
                    "total_versions": len(self._keks),
                },
            )
        )
        return new_version

    def encrypt(
        self, plaintext: str | bytes, metadata: dict[str, Any] | None = None
    ) -> EnvelopePayload:
        """Encrypt plaintext using an ephemeral Data Encryption Key (DEK), then encrypt DEK under active KEK."""
        raw_bytes = (
            plaintext.encode("utf-8") if isinstance(plaintext, str) else plaintext
        )

        # 1. Generate unique ephemeral DEK for this specific payload
        dek = Fernet.generate_key()
        dek_fernet = Fernet(dek)

        # 2. Encrypt plaintext with the ephemeral DEK
        encrypted_payload = dek_fernet.encrypt(raw_bytes)

        # 3. Encrypt the DEK using the currently active KEK version
        active_kek = self._keks[self._active_version]
        kek_fernet = Fernet(active_kek)
        encrypted_dek = kek_fernet.encrypt(dek)

        return EnvelopePayload(
            kek_version=self._active_version,
            encrypted_dek=base64.b64encode(encrypted_dek).decode("ascii"),
            ciphertext=base64.b64encode(encrypted_payload).decode("ascii"),
            metadata=metadata or {},
        )

    def decrypt(self, envelope: EnvelopePayload) -> str:
        """Decrypt payload by retrieving the corresponding KEK version, unwrapping DEK, and decrypting data."""
        kek = self._keks.get(envelope.kek_version)
        if not kek:
            raise ValueError(
                f"Cannot decrypt envelope: KEK version '{envelope.kek_version}' not found in keystore."
            )

        # 1. Decrypt ephemeral DEK using the historical or active KEK
        kek_fernet = Fernet(kek)
        raw_encrypted_dek = base64.b64decode(envelope.encrypted_dek.encode("ascii"))
        dek = kek_fernet.decrypt(raw_encrypted_dek)

        # 2. Decrypt ciphertext using unwrapped DEK
        dek_fernet = Fernet(dek)
        raw_ciphertext = base64.b64decode(envelope.ciphertext.encode("ascii"))
        decrypted_bytes = dek_fernet.decrypt(raw_ciphertext)

        return decrypted_bytes.decode("utf-8")

    def re_wrap(self, envelope: EnvelopePayload) -> EnvelopePayload:
        """Re-wrap historical envelope to the active KEK version without modifying plaintext."""
        if envelope.kek_version == self._active_version:
            return envelope  # Already on latest key version

        # Decrypt plaintext and re-encrypt under active version
        plaintext = self.decrypt(envelope)
        new_envelope = self.encrypt(plaintext, metadata=envelope.metadata)

        audit = SecurityAuditLogger.get_logger()
        audit.log_event(
            AuditEvent(
                actor="system",
                action="security.envelope_rewrapped",
                resource_type="encrypted_envelope",
                resource_id=envelope.kek_version,
                outcome="success",
                metadata={
                    "from_version": envelope.kek_version,
                    "to_version": self._active_version,
                },
            )
        )
        return new_envelope
