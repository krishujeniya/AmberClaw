"""Hardware Enclave capability discovery and diagnostic checks."""

import shutil
from pathlib import Path
from typing import Any


def check_nitro_enclaves_available() -> dict[str, Any]:
    """Check AWS Nitro Enclaves driver and CLI availability."""
    dev_path = Path("/dev/nitro_enclaves")
    has_dev = dev_path.exists()
    has_cli = shutil.which("nitro-cli") is not None
    return {
        "available": has_dev or has_cli,
        "cli_present": has_cli,
        "details": f"device={has_dev}, nitro-cli={has_cli}",
        "device_present": has_dev,
        "platform": "AWS Nitro Enclaves",
    }


def check_intel_sgx_available() -> dict[str, Any]:
    """Check Intel SGX / Gramine driver and tooling availability."""
    sgx_enclave = Path("/dev/sgx_enclave").exists()
    sgx_provision = Path("/dev/sgx_provision").exists()
    isgx = Path("/dev/isgx").exists()
    has_gramine = shutil.which("gramine-sgx") is not None
    has_sgx = sgx_enclave or sgx_provision or isgx
    return {
        "available": has_sgx or has_gramine,
        "details": f"sgx_dev={has_sgx}, gramine={has_gramine}",
        "device_present": has_sgx,
        "gramine_present": has_gramine,
        "platform": "Intel SGX / Gramine",
    }


def check_amd_sev_available() -> dict[str, Any]:
    """Check AMD SEV-SNP driver and hypervisor support."""
    sev_guest = Path("/dev/sev-guest").exists()
    sev_dev = Path("/dev/sev").exists()
    kvm_sev = False
    kvm_sev_path = Path("/sys/module/kvm_amd/parameters/sev")
    if kvm_sev_path.exists():
        try:
            content = kvm_sev_path.read_text().strip()
            kvm_sev = content in ("1", "Y", "y")
        except Exception:
            kvm_sev = False

    available = sev_guest or sev_dev or kvm_sev
    return {
        "available": available,
        "details": f"sev_dev={sev_guest or sev_dev}, kvm_sev={kvm_sev}",
        "device_present": sev_guest or sev_dev,
        "kvm_sev_enabled": kvm_sev,
        "platform": "AMD SEV-SNP",
    }


def get_enclave_diagnostics() -> dict[str, Any]:
    """Gather diagnostic status across all confidential computing platforms."""
    nitro = check_nitro_enclaves_available()
    sgx = check_intel_sgx_available()
    sev = check_amd_sev_available()

    hardware_found = nitro["available"] or sgx["available"] or sev["available"]

    return {
        "hardware_enclave_available": hardware_found,
        "platforms": {
            "nitro": nitro,
            "sev_snp": sev,
            "sgx": sgx,
            "simulated": {
                "available": True,
                "details": "AES-256-GCM + X25519 ECDH + SHA-384 Attestation",
                "platform": "Simulated Zero-Trust Enclave",
            },
        },
        "simulated_enclave_available": True,
    }
