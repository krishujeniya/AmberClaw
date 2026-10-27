"""Hardware Remote Attestation verification and generation."""

import json
import logging
from datetime import UTC, datetime

from amberclaw.security.enclave.crypto import EnclaveSigner
from amberclaw.security.enclave.models import (
    AttestationDocument,
    EnclaveMeasurement,
    EnclavePlatform,
)

logger = logging.getLogger(__name__)

MAX_CLOCK_SKEW_FUTURE_SEC = -60


def build_canonical_attestation_payload(  # noqa: PLR0913
    platform: str,
    enclave_id: str,
    pcr0: str,
    pcr1: str,
    pcr2: str,
    public_key_pem: str,
    nonce: str,
    timestamp_utc: str,
    user_data: str = "",
) -> bytes:
    """Build a deterministic JSON payload for digital signature calculation."""
    data = {
        "enclave_id": enclave_id,
        "nonce": nonce,
        "pcr0": pcr0,
        "pcr1": pcr1,
        "pcr2": pcr2,
        "platform": platform,
        "public_key_pem": public_key_pem.strip(),
        "timestamp_utc": timestamp_utc,
        "user_data": user_data,
    }
    return json.dumps(data, sort_keys=True).encode("utf-8")


class AttestationVerifier:
    """Validates remote attestation reports and cryptographic measurements."""

    def __init__(self, trusted_root_keys: dict[str, str] | None = None) -> None:
        """Args:
        trusted_root_keys: Mapping of platform name/id to trusted public key PEM.
        """
        self.trusted_root_keys = trusted_root_keys or {}

    def verify(  # noqa: PLR0911
        self,
        doc: AttestationDocument,
        expected_nonce: str | None = None,
        allowed_pcr0: list[str] | None = None,
        max_age_seconds: int = 300,
        platform_root_pubkey_pem: str | None = None,
    ) -> tuple[bool, str]:
        """Verify an AttestationDocument.

        Returns:
            (is_valid, error_reason)
        """
        # 1. Check Nonce (Anti-replay defense)
        if expected_nonce and doc.nonce != expected_nonce:
            return False, f"Nonce mismatch. Expected {expected_nonce}, got {doc.nonce}"

        # 2. Check Timestamp freshness
        try:
            doc_time = datetime.fromisoformat(doc.timestamp_utc)
            now_time = datetime.now(UTC)
            age = (now_time - doc_time).total_seconds()
            if age > max_age_seconds:
                return False, f"Attestation document expired. Age: {age:.1f}s > {max_age_seconds}s"
            if age < MAX_CLOCK_SKEW_FUTURE_SEC:
                return False, f"Attestation document timestamp in future: {doc.timestamp_utc}"
        except Exception as e:
            return False, f"Invalid timestamp format: {e}"

        # 3. Check PCR0 / MRENCLAVE measurement whitelist
        if allowed_pcr0 and doc.measurements.pcr0 not in allowed_pcr0:
            return False, (
                f"Untrusted enclave measurement PCR0 '{doc.measurements.pcr0}' "
                f"not in whitelist {allowed_pcr0}"
            )

        # 4. Verify Digital Signature
        pubkey = platform_root_pubkey_pem or self.trusted_root_keys.get(doc.platform.value)
        if pubkey:
            canonical_payload = build_canonical_attestation_payload(
                platform=doc.platform.value,
                enclave_id=doc.enclave_id,
                pcr0=doc.measurements.pcr0,
                pcr1=doc.measurements.pcr1,
                pcr2=doc.measurements.pcr2,
                public_key_pem=doc.public_key_pem,
                nonce=doc.nonce,
                timestamp_utc=doc.timestamp_utc,
                user_data=doc.user_data,
            )
            sig_valid = EnclaveSigner.verify_signature(pubkey, canonical_payload, doc.signature)
            if not sig_valid:
                return False, "Attestation signature verification failed against platform root key"

        return True, "Attestation verified successfully"


def create_attestation_document(  # noqa: PLR0913
    platform: EnclavePlatform,
    enclave_id: str,
    measurements: EnclaveMeasurement,
    public_key_pem: str,
    nonce: str,
    signer: EnclaveSigner,
    user_data: str = "",
) -> AttestationDocument:
    """Create a signed AttestationDocument using an EnclaveSigner."""
    ts = datetime.now(UTC).isoformat()
    canonical_payload = build_canonical_attestation_payload(
        platform=platform.value,
        enclave_id=enclave_id,
        pcr0=measurements.pcr0,
        pcr1=measurements.pcr1,
        pcr2=measurements.pcr2,
        public_key_pem=public_key_pem,
        nonce=nonce,
        timestamp_utc=ts,
        user_data=user_data,
    )
    sig = signer.sign_message(canonical_payload)

    return AttestationDocument(
        platform=platform,
        enclave_id=enclave_id,
        measurements=measurements,
        public_key_pem=public_key_pem,
        nonce=nonce,
        timestamp_utc=ts,
        signature=sig,
        certificate_chain=[signer.public_key_pem],
        user_data=user_data,
    )
