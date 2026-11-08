#!/usr/bin/env python3
"""Generates CycloneDX and SPDX Software Bill of Materials (SBOM) for AmberClaw.

Inventories the current installed environment, including development tools and
extras. This is not a lockfile or production-image inventory. License conclusions
require separate review; unrecognized declarations remain NOASSERTION.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import logging
import sys
import tomllib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from packaging.licenses import InvalidLicenseExpression, canonicalize_license_expression
from packaging.utils import canonicalize_name

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("sbom_generator")
SCOPE = "Installed Python environment, including development tools and optional extras; not a production-image or lockfile inventory."


def project_version() -> str:
    manifest = Path(__file__).resolve().parents[1] / "pyproject.toml"
    return str(
        tomllib.loads(manifest.read_text(encoding="utf-8"))["project"]["version"]
    )


def purl(component: dict[str, str]) -> str:
    return f"pkg:pypi/{canonicalize_name(component['name'])}@{quote(component['version'], safe='')}"


def license_expression(value: str) -> str:
    try:
        return str(canonicalize_license_expression(value))
    except InvalidLicenseExpression:
        return "NOASSERTION"


def generate_cyclonedx(components: list[dict[str, str]]) -> dict[str, Any]:
    """Generates CycloneDX 1.5 JSON formatted SBOM."""
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tools": [
                {
                    "vendor": "AmberClaw",
                    "name": "amberclaw-sbom",
                    "version": project_version(),
                }
            ],
            "component": {
                "type": "application",
                "name": "amberclaw",
                "version": project_version(),
                "description": "Autonomous AI Agent Operating System",
            },
            "properties": [{"name": "amberclaw:inventory-scope", "value": SCOPE}],
        },
        "components": [
            {
                "type": "library",
                "name": c["name"],
                "version": c["version"],
                "bom-ref": purl(c),
                "purl": purl(c),
                "licenses": [{"expression": license_expression(c.get("license", ""))}]
                if license_expression(c.get("license", "")) != "NOASSERTION"
                else [],
            }
            for c in components
        ],
    }


def generate_spdx(components: list[dict[str, str]]) -> dict[str, Any]:
    """Generates SPDX 2.3 JSON formatted SBOM."""
    doc_id = "SPDXRef-DOCUMENT"
    spdx_packages = []

    for idx, c in enumerate(components, start=1):
        spdx_packages.append(
            {
                "SPDXID": f"SPDXRef-Package-{idx}",
                "name": c["name"],
                "versionInfo": c["version"],
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": license_expression(c.get("license", "")),
                "copyrightText": "NOASSERTION",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": purl(c),
                    }
                ],
            }
        )

    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": doc_id,
        "name": "AmberClaw-SPDX-SBOM",
        "documentNamespace": f"https://amberclaw.ai/spdx/{project_version()}/{uuid.uuid4()}",
        "comment": SCOPE,
        "creationInfo": {
            "created": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "creators": [f"Tool: amberclaw-sbom-{project_version()}"],
        },
        "packages": spdx_packages,
        "relationships": [
            {
                "spdxElementId": doc_id,
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": package["SPDXID"],
            }
            for package in spdx_packages
        ],
    }


def collect_installed_packages() -> list[dict[str, str]]:
    """Gathers installed packages and their declared licenses."""
    packages = []
    seen = set()

    for dist in importlib.metadata.distributions():
        name = dist.metadata.get("Name")
        if not name:
            continue
        cleaned_name = canonicalize_name(name.strip())
        if cleaned_name in seen:
            continue
        seen.add(cleaned_name)

        version = dist.metadata.get("Version", "unknown")
        license_name = dist.metadata.get("License-Expression") or dist.metadata.get(
            "License", ""
        )

        packages.append(
            {
                "name": cleaned_name,
                "version": version,
                "license": license_expression(license_name),
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
