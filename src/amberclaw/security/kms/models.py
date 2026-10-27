"""Data models and schemas for Cloud KMS and HSM Secret Management."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class KMSProviderType(StrEnum):
    """Supported Cloud KMS and Key Management Service backends."""

    AWS_KMS = "aws_kms"
    GCP_KMS = "gcp_kms"
    VAULT_TRANSIT = "vault_transit"
    LOCAL_ENVELOPE = "local_envelope"


class KMSConfig(BaseModel):
    """Configuration for Cloud KMS integration."""

    provider: KMSProviderType = Field(default=KMSProviderType.LOCAL_ENVELOPE)
    key_id: str = Field(default="alias/amberclaw-master-key", description="KMS Key ARN, Key Resource Name, or Transit Key Name")
    region: str = Field(default="us-east-1", description="Cloud provider region")
    endpoint_url: str | None = Field(default=None, description="Custom KMS/Vault endpoint URL (e.g. for LocalStack or private Vault)")
    vault_token: str | None = Field(default=None, description="Vault token for HashiCorp Transit engine")
    dek_cache_ttl_sec: int = Field(default=300, ge=0, le=86400, description="Data Encryption Key memory cache TTL in seconds")
    auto_rotate_days: int = Field(default=90, ge=1, le=365, description="Automatic key rotation recommendation window")


class EncryptedDataEnvelope(BaseModel):
    """Cryptographic envelope storing encrypted payload and encrypted DEK."""

    provider: KMSProviderType
    key_id: str
    encrypted_dek_b64: str = Field(..., description="Encrypted Data Encryption Key (DEK) wrapped by Master Key")
    iv_b64: str = Field(..., description="12-byte initialization vector / nonce for AES-256-GCM")
    ciphertext_b64: str = Field(..., description="Ciphertext of the secret payload")
    tag_b64: str = Field(..., description="16-byte authentication tag for AES-256-GCM")
    created_at_utc: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    version: str = "1.0"
    metadata: dict[str, Any] = Field(default_factory=dict)
