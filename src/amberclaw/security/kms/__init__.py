"""Cloud KMS and Key Management Service Module."""

from amberclaw.security.kms.manager import KMSSecretManager
from amberclaw.security.kms.models import (
    EncryptedDataEnvelope,
    KMSConfig,
    KMSProviderType,
)
from amberclaw.security.kms.provider import (
    AWSKMSProvider,
    BaseKMSProvider,
    GCPKMSProvider,
    LocalEnvelopeKMSProvider,
    VaultTransitProvider,
    get_kms_provider,
)

__all__ = [
    "AWSKMSProvider",
    "BaseKMSProvider",
    "EncryptedDataEnvelope",
    "GCPKMSProvider",
    "KMSConfig",
    "KMSProviderType",
    "KMSSecretManager",
    "LocalEnvelopeKMSProvider",
    "VaultTransitProvider",
    "get_kms_provider",
]
