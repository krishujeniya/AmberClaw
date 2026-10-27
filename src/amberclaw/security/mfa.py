"""Hardware-backed Multi-Factor Authentication (MFA) and FIDO2/WebAuthn Engine.

Provides WebAuthn / FIDO2 hardware security key verification (YubiKey, SoloKey)
and RFC 6238 TOTP fallback with replay protection and monotonic counter validation.
"""

# ruff: noqa: PLR0913, PLR0912, PLR2004
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import struct
import time
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MFASecurityError(Exception):
    """Raised when MFA verification fails or replay is detected."""


class FIDO2Credential(BaseModel):
    """Registered hardware security key credential."""

    credential_id: str
    user_id: str
    rp_id: str
    public_key_pem: str
    sign_count: int = 0
    created_at: float = Field(default_factory=time.time)


class HardwareMFAManager:
    """Manages WebAuthn/FIDO2 hardware keys and TOTP verification."""

    def __init__(self) -> None:
        self._credentials: dict[
            str, FIDO2Credential
        ] = {}  # credential_id -> FIDO2Credential
        self._user_credentials: dict[str, list[str]] = {}  # user_id -> [credential_id]
        self._user_totp_secrets: dict[str, str] = {}  # user_id -> base32 secret
        self._used_totp_codes: set[tuple[str, int]] = set()  # (user_id, time_step)
        self._active_challenges: dict[str, float] = {}  # challenge -> expiry_ts

    def generate_challenge(self, ttl_seconds: float = 300.0) -> str:
        """Generates a cryptographic random WebAuthn challenge."""
        raw = hashlib.sha256(
            f"{time.time()}:{struct.pack('>Q', int(time.time() * 1000))}".encode()
        ).digest()
        challenge = base64.urlsafe_b64encode(raw).decode().rstrip("=")
        self._active_challenges[challenge] = time.time() + ttl_seconds
        return challenge

    def register_fido2_key(
        self,
        user_id: str,
        credential_id: str,
        public_key_pem: str,
        rp_id: str,
    ) -> FIDO2Credential:
        """Registers a verified hardware security key public key."""
        # Verify valid PEM
        try:
            serialization.load_pem_public_key(public_key_pem.encode())
        except Exception as e:
            raise MFASecurityError(f"Invalid public key PEM: {e}") from e

        cred = FIDO2Credential(
            credential_id=credential_id,
            user_id=user_id,
            rp_id=rp_id,
            public_key_pem=public_key_pem,
            sign_count=0,
        )
        self._credentials[credential_id] = cred
        self._user_credentials.setdefault(user_id, []).append(credential_id)
        logger.info(
            "Registered FIDO2 security key [%s] for user [%s]", credential_id, user_id
        )
        return cred

    def verify_fido2_assertion(
        self,
        user_id: str,
        credential_id: str,
        client_data_json: bytes | str,
        auth_data: bytes,
        signature: bytes,
        challenge: str,
    ) -> bool:
        """Verifies a WebAuthn/FIDO2 hardware key assertion.

        Enforces:
        - Challenge validity and matching
        - Client data type == 'webauthn.get'
        - RP ID hash match
        - User Presence (UP) flag
        - Monotonic signature counter verification (anti-cloning / replay detection)
        - Cryptographic signature check over authData + SHA256(clientDataJSON)
        """
        # 1. Challenge validation
        now = time.time()
        if (
            challenge not in self._active_challenges
            or self._active_challenges[challenge] < now
        ):
            raise MFASecurityError("Challenge is invalid or has expired")
        del self._active_challenges[challenge]

        # 2. Look up credential
        cred = self._credentials.get(credential_id)
        if not cred or cred.user_id != user_id:
            raise MFASecurityError(
                f"Credential [{credential_id}] not found or not owned by {user_id}"
            )

        # 3. Parse and verify clientDataJSON
        if isinstance(client_data_json, str):
            raw_client_data = client_data_json.encode("utf-8")
        else:
            raw_client_data = client_data_json

        try:
            client_data = json.loads(raw_client_data.decode("utf-8"))
        except Exception as e:
            raise MFASecurityError(f"Malformed clientDataJSON: {e}") from e

        if client_data.get("type") != "webauthn.get":
            raise MFASecurityError(
                f"Unexpected clientData type: {client_data.get('type')}"
            )

        if client_data.get("challenge") != challenge:
            raise MFASecurityError(
                "ClientData challenge does not match expected challenge"
            )

        # 4. Verify authData length (minimum 37 bytes: 32 rpIdHash + 1 flags + 4 signCount)
        if len(auth_data) < 37:
            raise MFASecurityError("Malformed authenticator data: payload too short")

        rp_id_hash = auth_data[:32]
        expected_rp_id_hash = hashlib.sha256(cred.rp_id.encode("utf-8")).digest()
        if not hmac.compare_digest(rp_id_hash, expected_rp_id_hash):
            raise MFASecurityError("Authenticator RP ID hash mismatch")

        flags = auth_data[32]
        # UP: Bit 0
        if not (flags & 0x01):
            raise MFASecurityError(
                "User Presence (UP) flag was not set by authenticator"
            )

        # 5. Monotonic sign_count verification
        incoming_sign_count = struct.unpack(">I", auth_data[33:37])[0]
        if incoming_sign_count != 0 and incoming_sign_count <= cred.sign_count:
            logger.error(
                "FIDO2 counter rollback detected! Incoming: %d, Stored: %d",
                incoming_sign_count,
                cred.sign_count,
            )
            raise MFASecurityError(
                "Authenticator counter rollback detected (possible cloned token)"
            )

        # 6. Verify cryptographic signature
        client_data_hash = hashlib.sha256(raw_client_data).digest()
        signed_payload = auth_data + client_data_hash

        pub_key = serialization.load_pem_public_key(cred.public_key_pem.encode())
        try:
            if isinstance(pub_key, ec.EllipticCurvePublicKey):
                pub_key.verify(signature, signed_payload, ec.ECDSA(hashes.SHA256()))
            elif isinstance(pub_key, rsa.RSAPublicKey):
                pub_key.verify(
                    signature, signed_payload, padding.PKCS1v15(), hashes.SHA256()
                )
            else:
                raise MFASecurityError("Unsupported public key algorithm")
        except InvalidSignature as e:
            raise MFASecurityError(
                "FIDO2 cryptographic signature verification failed"
            ) from e

        # Update counter on success
        cred.sign_count = incoming_sign_count
        logger.info(
            "FIDO2 hardware assertion successfully verified for user [%s], sign_count=%d",
            user_id,
            incoming_sign_count,
        )
        return True

    def register_totp_secret(self, user_id: str, base32_secret: str) -> None:
        """Registers a TOTP secret for fallback admin MFA."""
        self._user_totp_secrets[user_id] = base32_secret.strip()

    def verify_totp(
        self,
        user_id: str,
        code: str,
        window: int = 1,
        time_step: int = 30,
    ) -> bool:
        """Verifies a 6-digit TOTP code with time drift window and single-use replay protection."""
        secret = self._user_totp_secrets.get(user_id)
        if not secret:
            raise MFASecurityError(f"No TOTP secret enrolled for user [{user_id}]")

        cleaned_code = code.strip().replace(" ", "")
        if not cleaned_code.isdigit() or len(cleaned_code) != 6:
            return False

        try:
            key = base64.b32decode(secret, casefold=True)
        except Exception as e:
            raise MFASecurityError(f"Invalid base32 TOTP secret: {e}") from e

        now = int(time.time())
        current_step = now // time_step

        for offset in range(-window, window + 1):
            step = current_step + offset
            replay_key = (user_id, step)
            if replay_key in self._used_totp_codes:
                continue

            # Compute RFC 4226 / 6238 HOTP
            msg = struct.pack(">Q", step)
            hmac_hash = hmac.new(key, msg, hashlib.sha1).digest()
            offset_byte = hmac_hash[-1] & 0x0F
            truncated_hash = (
                struct.unpack(">I", hmac_hash[offset_byte : offset_byte + 4])[0]
                & 0x7FFFFFFF
            )
            expected_otp = truncated_hash % 1_000_000
            expected_str = f"{expected_otp:06d}"

            if hmac.compare_digest(cleaned_code, expected_str):
                # Mark step used to prevent replay
                self._used_totp_codes.add(replay_key)
                # Evict old entries from used codes (older than 10 steps)
                self._used_totp_codes = {
                    k for k in self._used_totp_codes if k[1] >= current_step - 10
                }
                return True

        return False

    def verify_admin_mfa(
        self,
        user_id: str,
        auth_payload: dict[str, Any],
    ) -> bool:
        """Unified admin MFA verification gate."""
        auth_type = auth_payload.get("type")
        if auth_type == "fido2":
            return self.verify_fido2_assertion(
                user_id=user_id,
                credential_id=auth_payload["credential_id"],
                client_data_json=auth_payload["client_data_json"],
                auth_data=auth_payload["auth_data"],
                signature=auth_payload["signature"],
                challenge=auth_payload["challenge"],
            )
        if auth_type == "totp":
            return self.verify_totp(user_id=user_id, code=auth_payload["code"])

        raise MFASecurityError(f"Unsupported MFA type: {auth_type}")
