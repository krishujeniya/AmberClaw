"""Data models and schemas for Zero-Trust Hardware Enclave Sandboxing."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EnclavePlatform(StrEnum):
    """Supported confidential computing and hardware enclave platforms."""

    NITRO = "nitro"  # AWS Nitro Enclaves (EIF + VSOCK)
    SGX = "sgx"  # Intel SGX / Gramine (Protected Memory Enclave)
    SEV_SNP = "sev_snp"  # AMD SEV-SNP (Secure Encrypted Virtualization)
    SIMULATED = "simulated"  # Cryptographically verified software enclave


class EnclaveStatus(StrEnum):
    """Lifecycle status of an enclave instance."""

    PROVISIONING = "provisioning"
    ATTESTING = "attesting"
    READY = "ready"
    EXECUTING = "executing"
    TERMINATED = "terminated"
    FAILED = "failed"


class EnclaveMeasurement(BaseModel):
    """Cryptographic measurements (PCRs / MRENCLAVE / Launch Digests)."""

    pcr0: str = Field(..., description="Hash of the enclave image / kernel / boot code (MRENCLAVE)")
    pcr1: str = Field(default="", description="Hash of the enclave runtime / OS / configuration")
    pcr2: str = Field(default="", description="Hash of the enclave application / signature")
    hash_algorithm: str = Field(default="sha384", description="Cryptographic hashing algorithm (sha256, sha384, sha512)")


class AttestationDocument(BaseModel):
    """Signed hardware remote attestation report."""

    platform: EnclavePlatform
    enclave_id: str
    measurements: EnclaveMeasurement
    public_key_pem: str = Field(..., description="Enclave ephemeral public key for secure channel handshake")
    nonce: str = Field(..., description="Fresh challenge nonce provided by the host verifier")
    timestamp_utc: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    signature: str = Field(..., description="Digital signature of attestation document by platform root key")
    certificate_chain: list[str] = Field(default_factory=list, description="PEM certificate chain up to platform CA")
    user_data: str = Field(default="", description="Custom user/session metadata embedded in hardware report")


class EnclaveConfig(BaseModel):
    """Configuration for provisioning and running an enclave sandbox."""

    platform: EnclavePlatform = Field(default=EnclavePlatform.SIMULATED)
    memory_mb: int = Field(default=512, ge=64, le=16384, description="Enclave dedicated memory cap in MB")
    vcpu_count: int = Field(default=2, ge=1, le=32, description="Dedicated vCPUs allocated to the enclave")
    strict_attestation: bool = Field(default=True, description="Enforce remote attestation and measurement checks")
    allowed_pcr0_measurements: list[str] = Field(
        default_factory=list,
        description="Whitelist of permitted PCR0 / MRENCLAVE hashes. If empty, any valid signature is allowed.",
    )
    zero_egress: bool = Field(default=True, description="Strictly prohibit external TCP/IP egress; VSOCK only")
    vsock_cid: int | None = Field(default=None, description="Context ID for AF_VSOCK communication")
    vsock_port: int = Field(default=8000, description="VSOCK communication port")
    command_timeout_sec: int = Field(default=30, ge=1, le=300, description="Maximum execution timeout per command")


class EnclaveExecutionRequest(BaseModel):
    """Payload sent into the enclave across the secure boundary."""

    request_id: str
    command_type: str = Field(..., description="'python' or 'bash'")
    payload: str = Field(..., description="Code or shell script to execute")
    env_vars: dict[str, str] = Field(default_factory=dict)
    timeout_sec: int = 30
    timestamp_utc: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class EnclaveExecutionResponse(BaseModel):
    """Execution output returned from the enclave across the secure boundary."""

    request_id: str
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float
    sealed_token: str = Field(default="", description="Cryptographic proof/token of execution within enclave")
    status: str = "success"
    extra: dict[str, Any] = Field(default_factory=dict)
