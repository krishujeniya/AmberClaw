"""Hardware Enclave and Confidential Computing Subsystem."""

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
    AttestationDocument,
    EnclaveConfig,
    EnclaveExecutionRequest,
    EnclaveExecutionResponse,
    EnclaveMeasurement,
    EnclavePlatform,
    EnclaveStatus,
)

__all__ = [
    "AttestationDocument",
    "AttestationVerifier",
    "EnclaveConfig",
    "EnclaveExecutionRequest",
    "EnclaveExecutionResponse",
    "EnclaveKeyAgreement",
    "EnclaveManager",
    "EnclaveMeasurement",
    "EnclavePlatform",
    "EnclaveSecureChannel",
    "EnclaveSigner",
    "EnclaveStatus",
    "compute_measurement_hash",
    "create_attestation_document",
    "generate_nonce",
    "get_enclave_diagnostics",
    "zeroize_buffer",
]
