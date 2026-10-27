#!/usr/bin/env python3
"""Generates CycloneDX and SPDX Software Bill of Materials (SBOM) for AmberClaw.

Collects package metadata, versions, licenses, and purl references directly
from installed distribution metadata and uv lockfile without external dependencies.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import logging
import sys
import time
import uuid
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("sbom_generator")


def generate_cyclonedx(components: list[dict[str, str]]) -> dict:
    """Generates CycloneDX 1.5 JSON formatted SBOM."""
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tools": [
                {"vendor": "AmberClaw", "name": "amberclaw-sbom", "version": "1.0.0"}
            ],
            "component": {
                "type": "application",
                "name": "amberclaw",
                "version": "1.0.0",
                "description": "Autonomous AI Agent Operating System",
            },
        },
        "components": [
            {
                "type": "library",
                "name": c["name"],
                "version": c["version"],
                "purl": f"pkg:pypi/{c['name']}@{c['version']}",
                "licenses": [{"license": {"name": c["license"]}}]
                if c.get("license")
                else [],
            }
            for c in components
        ],
    }


def generate_spdx(components: list[dict[str, str]]) -> dict:
    """Generates SPDX 2.3 JSON formatted SBOM."""
    doc_id = f"SPDXRef-DOCUMENT-{uuid.uuid4().hex[:8]}"
    spdx_packages = []

    for idx, c in enumerate(components, start=1):
        spdx_packages.append(
            {
                "SPDXID": f"SPDXRef-Package-{idx}",
                "name": c["name"],
                "versionInfo": c["version"],
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": c.get("license") or "NOASSERTION",
                "licenseDeclared": c.get("license") or "NOASSERTION",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": f"pkg:pypi/{c['name']}@{c['version']}",
                    }
                ],
            }
        )

    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": doc_id,
        "name": "AmberClaw-SPDX-SBOM",
        "documentNamespace": f"https://amberclaw.ai/spdx/{doc_id}",
        "creationInfo": {
            "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "creators": ["Tool: amberclaw-sbom-1.0.0", "Organization: AmberClaw Core"],
        },
        "packages": spdx_packages,
    }


def collect_installed_packages() -> list[dict[str, str]]:
    """Gathers installed packages and their declared licenses."""
    packages = []
    seen = set()

    for dist in importlib.metadata.distributions():
        name = dist.metadata.get("Name")
        if not name:
            continue
        cleaned_name = name.strip().lower()
        if cleaned_name in seen:
            continue
        seen.add(cleaned_name)

        version = dist.metadata.get("Version", "unknown")
        license_name = dist.metadata.get("License", "UNKNOWN")

        packages.append(
            {
                "name": name,
                "version": version,
                "license": license_name.split("\n")[0].strip()
                if license_name
                else "UNKNOWN",
            }
        )

    packages.sort(key=lambda x: x["name"].lower())
    return packages


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate CycloneDX and SPDX SBOMs.")
    parser.add_argument(
        "--out-dir",
        default="dist",
        help="Directory to save SBOM artifacts (default: dist)",
    )
    args = parser.parse_args()

    out_path = Path(args.out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    packages = collect_installed_packages()
    logger.info("Discovered %d installed packages", len(packages))

    # 1. CycloneDX SBOM
    cyclonedx_sbom = generate_cyclonedx(packages)
    cdx_file = out_path / "amberclaw.cyclonedx.json"
    cdx_file.write_text(json.dumps(cyclonedx_sbom, indent=2), encoding="utf-8")
    logger.info("Wrote CycloneDX SBOM to %s", cdx_file)

    # 2. SPDX SBOM
    spdx_sbom = generate_spdx(packages)
    spdx_file = out_path / "amberclaw.spdx.json"
    spdx_file.write_text(json.dumps(spdx_sbom, indent=2), encoding="utf-8")
    logger.info("Wrote SPDX SBOM to %s", spdx_file)

    return 0


if __name__ == "__main__":
    sys.exit(main())
