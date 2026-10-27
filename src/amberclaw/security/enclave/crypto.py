"""Cryptographic primitives and secure boundary encryption for Hardware Enclaves."""

import base64
import ctypes
import hashlib
import json
import os
import secrets
from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

AES_256_KEY_BYTES = 32
MIN_ENVELOPE_BYTES = 28  # 12-byte nonce + 16-byte GCM tag


def generate_nonce(length_bytes: int = 32) -> str:
    """Generate a high-entropy hex nonce for attestation challenge-response."""
    return secrets.token_hex(length_bytes)


def zeroize_buffer(buf: bytearray | memoryview) -> None:
    """Securely overwrite sensitive memory buffers with zeros."""
    if isinstance(buf, (bytearray, memoryview)):
        ctypes.memset((ctypes.c_char * len(buf)).from_buffer(buf), 0, len(buf))


class EnclaveKeyAgreement:
    """ECDH key agreement across host and enclave boundary using X25519."""

    def __init__(self, private_key: x25519.X25519PrivateKey | None = None) -> None:
        self._private_key = private_key or x25519.X25519PrivateKey.generate()
        self._public_key = self._private_key.public_key()

    @property
    def public_key_pem(self) -> str:
        """Export public key as PEM string."""
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

    @classmethod
    def load_public_key(cls, pem_str: str) -> x25519.X25519PublicKey:
        """Load an X25519 public key from PEM string."""
        key = serialization.load_pem_public_key(pem_str.encode("utf-8"), backend=default_backend())
        if not isinstance(key, x25519.X25519PublicKey):
            raise ValueError("Provided PEM is not an X25519 public key")
        return key

    def derive_shared_secret(self, peer_public_key: x25519.X25519PublicKey | str) -> bytes:
        """Perform ECDH exchange and derive a 256-bit AES-GCM symmetric session key."""
        if isinstance(peer_public_key, str):
            peer_pub = self.load_public_key(peer_public_key)
        else:
            peer_pub = peer_public_key

        raw_secret = self._private_key.exchange(peer_pub)

        # HKDF expansion to 32 bytes (256 bits)
        return HKDF(
            algorithm=hashes.SHA256(),
            length=AES_256_KEY_BYTES,
            salt=b"amberclaw-enclave-channel-v1",
            info=b"aes-256-gcm-session-key",
            backend=default_backend(),
        ).derive(raw_secret)


class EnclaveSecureChannel:
    """AES-256-GCM authenticated encryption channel across the enclave barrier."""

    def __init__(self, session_key: bytes) -> None:
        if len(session_key) != AES_256_KEY_BYTES:
            raise ValueError("AES-256 session key must be exactly 32 bytes")
        self._key = session_key
        self._aesgcm = AESGCM(self._key)

    def encrypt_payload(self, data: str | dict[str, Any], aad: bytes = b"") -> str:
        """Encrypt JSON or text payload with AES-256-GCM and return base64 string.
        Format: base64(nonce_12b + ciphertext_and_tag).
        """
        if isinstance(data, dict):
            raw_bytes = json.dumps(data, sort_keys=True).encode("utf-8")
        else:
            raw_bytes = data.encode("utf-8")

        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, raw_bytes, aad or None)
        envelope = nonce + ciphertext
        return base64.b64encode(envelope).decode("utf-8")

    def decrypt_payload(self, encrypted_b64: str, aad: bytes = b"") -> str:
        """Decrypt AES-256-GCM payload and return UTF-8 string."""
        envelope = base64.b64decode(encrypted_b64)
        if len(envelope) < MIN_ENVELOPE_BYTES:
            raise ValueError("Ciphertext envelope is truncated")

        nonce = envelope[:12]
        ciphertext = envelope[12:]
        decrypted = self._aesgcm.decrypt(nonce, ciphertext, aad or None)
        return decrypted.decode("utf-8")

    def close(self) -> None:
        """Zeroize key buffer."""
        key_view = bytearray(self._key)
        zeroize_buffer(key_view)


class EnclaveSigner:
    """ECDSA P-256 signer for attestation reports and tamper-proof tokens."""

    def __init__(self, private_key: ec.EllipticCurvePrivateKey | None = None) -> None:
        self._private_key = private_key or ec.generate_private_key(ec.SECP256R1(), default_backend())
        self._public_key = self._private_key.public_key()

    @property
    def public_key_pem(self) -> str:
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

    def sign_message(self, message: bytes | str) -> str:
        """Sign a message and return base64-encoded signature."""
        msg_bytes = message.encode("utf-8") if isinstance(message, str) else message
        signature = self._private_key.sign(msg_bytes, ec.ECDSA(hashes.SHA256()))
        return base64.b64encode(signature).decode("utf-8")

    @classmethod
    def verify_signature(cls, public_key_pem: str, message: bytes | str, signature_b64: str) -> bool:
        """Verify ECDSA P-256 signature using public key PEM."""
        msg_bytes = message.encode("utf-8") if isinstance(message, str) else message
        sig_bytes = base64.b64decode(signature_b64)
        try:
            pub_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"), backend=default_backend())
            if not isinstance(pub_key, ec.EllipticCurvePublicKey):
                return False
            pub_key.verify(sig_bytes, msg_bytes, ec.ECDSA(hashes.SHA256()))
            return True
        except Exception:
            return False


def compute_measurement_hash(data: bytes | str, algorithm: str = "sha384") -> str:
    """Compute cryptographic hash of code/runtime image for measurement calculation."""
    data_bytes = data.encode("utf-8") if isinstance(data, str) else data
    if algorithm.lower() == "sha256":
        return hashlib.sha256(data_bytes).hexdigest()
    if algorithm.lower() == "sha512":
        return hashlib.sha512(data_bytes).hexdigest()
    return hashlib.sha384(data_bytes).hexdigest()
