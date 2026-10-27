"""Service-to-service mutual TLS (mTLS) configuration and verification engine.

Provides zero-trust authenticated transport for AmberClaw microservices,
subagent IPC, and cluster internal API communication.
"""

from __future__ import annotations

import datetime
import logging
import ssl
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MTLSSecurityError(Exception):
    """Raised when mTLS configuration or certificate verification fails."""


class MTLSConfig(BaseModel):
    """Configuration options for mutual TLS authentication."""

    ca_cert_path: Path | str = Field(
        ..., description="Path to trusted CA certificate chain"
    )
    cert_path: Path | str = Field(..., description="Path to local service certificate")
    key_path: Path | str = Field(..., description="Path to local service private key")
    key_password: str | None = Field(
        default=None, description="Optional password for private key"
    )
    ciphers: str | None = Field(
        default=None,
        description="OpenSSL cipher suite specification. Defaults to high-security modern ciphers.",
    )
    min_tls_version: ssl.TLSVersion = Field(
        default=ssl.TLSVersion.TLSv1_3,
        description="Minimum permitted TLS version (defaults to TLS 1.3)",
    )
    verify_peer: bool = Field(
        default=True,
        description="Whether mutual verification is enforced (CERT_REQUIRED)",
    )
    allowed_peer_identities: list[str] = Field(
        default_factory=list,
        description="List of allowed Common Names (CN) or SAN DNS names for peer verification",
    )


def create_server_ssl_context(config: MTLSConfig) -> ssl.SSLContext:
    """Builds a secure SSLContext for servers enforcing client mTLS certificates."""
    ca_file = Path(config.ca_cert_path).resolve()
    cert_file = Path(config.cert_path).resolve()
    key_file = Path(config.key_path).resolve()

    if not ca_file.is_file():
        raise MTLSSecurityError(f"CA certificate file not found: {ca_file}")
    if not cert_file.is_file():
        raise MTLSSecurityError(f"Server certificate file not found: {cert_file}")
    if not key_file.is_file():
        raise MTLSSecurityError(f"Server private key file not found: {key_file}")

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = config.min_tls_version

    if config.ciphers:
        ctx.set_ciphers(config.ciphers)

    # Require client certificate verification
    if config.verify_peer:
        ctx.verify_mode = ssl.CERT_REQUIRED
    else:
        ctx.verify_mode = ssl.CERT_NONE

    ctx.load_verify_locations(cafile=str(ca_file))
    ctx.load_cert_chain(
        certfile=str(cert_file),
        keyfile=str(key_file),
        password=config.key_password,
    )

    return ctx


def create_client_ssl_context(config: MTLSConfig) -> ssl.SSLContext:
    """Builds a secure SSLContext for clients presenting mutual certificates to servers."""
    ca_file = Path(config.ca_cert_path).resolve()
    cert_file = Path(config.cert_path).resolve()
    key_file = Path(config.key_path).resolve()

    if not ca_file.is_file():
        raise MTLSSecurityError(f"CA certificate file not found: {ca_file}")
    if not cert_file.is_file():
        raise MTLSSecurityError(f"Client certificate file not found: {cert_file}")
    if not key_file.is_file():
        raise MTLSSecurityError(f"Client private key file not found: {key_file}")

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = config.min_tls_version

    if config.ciphers:
        ctx.set_ciphers(config.ciphers)

    ctx.verify_mode = ssl.CERT_REQUIRED if config.verify_peer else ssl.CERT_NONE
    ctx.load_verify_locations(cafile=str(ca_file))
    ctx.load_cert_chain(
        certfile=str(cert_file),
        keyfile=str(key_file),
        password=config.key_password,
    )

    return ctx


def verify_peer_identity(
    peer_cert: dict[str, Any] | None,
    allowed_identities: list[str] | set[str] | None = None,
) -> bool:
    """Validates peer certificate identity against an allowlist of Common Names or SANs."""
    if not peer_cert:
        return False

    if not allowed_identities:
        return True

    allowed_set = set(allowed_identities)

    # Check Common Name (CN)
    subject = peer_cert.get("subject", ())
    for rdn in subject:
        for key, value in rdn:
            if key == "commonName" and value in allowed_set:
                return True

    # Check Subject Alternative Names (SANs)
    sans = peer_cert.get("subjectAltName", ())
    return any(san_val in allowed_set for _san_type, san_val in sans)


def generate_mtls_test_pki(output_dir: Path | str) -> dict[str, Path]:
    """Generates an in-memory or on-disk CA, server, and client certificate bundle for testing.

    Returns dict mapping artifact names to their file paths.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 1. Generate Root CA
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AmberClaw Root Authority"),
            x509.NameAttribute(NameOID.COMMON_NAME, "AmberClaw Root CA"),
        ]
    )
    now = datetime.datetime.now(datetime.UTC)
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_subject)
        .issuer_name(ca_subject)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )

    ca_cert_file = out / "ca.crt"
    ca_key_file = out / "ca.key"
    ca_cert_file.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    ca_key_file.write_bytes(
        ca_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )

    # Helper to generate entity cert signed by CA
    def _create_entity(
        name: str, common_name: str, dns_sans: list[str]
    ) -> tuple[Path, Path]:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AmberClaw Cluster"),
                x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            ]
        )
        san_extensions = [x509.DNSName(dns) for dns in dns_sans]
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(ca_subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=90))
            .add_extension(
                x509.SubjectAlternativeName(san_extensions),
                critical=False,
            )
            .sign(ca_key, hashes.SHA256())
        )
        cert_p = out / f"{name}.crt"
        key_p = out / f"{name}.key"
        cert_p.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        key_p.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        return cert_p, key_p

    srv_cert, srv_key = _create_entity(
        "server", "amberclaw-gateway", ["localhost", "amberclaw-gateway"]
    )
    cli_cert, cli_key = _create_entity(
        "client", "amberclaw-worker", ["localhost", "amberclaw-worker"]
    )

    return {
        "ca_cert": ca_cert_file,
        "ca_key": ca_key_file,
        "server_cert": srv_cert,
        "server_key": srv_key,
        "client_cert": cli_cert,
        "client_key": cli_key,
    }
