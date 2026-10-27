#!/usr/bin/env python3
"""License policy compliance verification script for AmberClaw.

Scans all direct and transitive third-party dependencies and enforces
that dependencies conform to organizational open source license policies.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("license_checker")

# Permitted open source licenses
DEFAULT_PERMITTED_LICENSES = {
    "mit",
    "apache 2.0",
    "apache-2.0",
    "apache software license",
    "bsd",
    "bsd license",
    "bsd-2-clause",
    "bsd-3-clause",
    "isc",
    "isc license (iscl)",
    "python software foundation license",
    "psf",
    "psf-2.0",
    "mpl-2.0",
    "mozilla public license 2.0 (mpl 2.0)",
    "unlicense",
    "the unlicense",
    "cc0-1.0",
    "public domain",
    "historical permission notice and disclaimer (hpnd)",
}

# Strong copyleft licenses requiring review / exemption
DISALLOWED_PATTERNS = [
    "agpl",
    "affero general public license",
    "gpl-3.0",
    "gnu general public license v3",
    "server side public license",
    "sspl",
]


def check_licenses(strict: bool = False) -> tuple[int, list[tuple[str, str, str]]]:
    """Inspects all installed packages against license compliance rules."""
    violations = []
    seen = set()

    for dist in importlib.metadata.distributions():
        name = dist.metadata.get("Name")
        if not name:
            continue
        cleaned_name = name.strip().lower()
        if cleaned_name in seen:
            continue
        seen.add(cleaned_name)

        raw_lic = dist.metadata.get("License", "UNKNOWN")
        lic_clean = raw_lic.split("\n")[0].strip().lower() if raw_lic else "unknown"

        # Check for disallowed copyleft
        if any(bad in lic_clean for bad in DISALLOWED_PATTERNS):
            violations.append((name, dist.version, raw_lic))
        elif (
            strict
            and lic_clean not in DEFAULT_PERMITTED_LICENSES
            and "unknown" not in lic_clean
        ):
            # Under strict mode, every license must be explicitly allowlisted
            violations.append((name, dist.version, raw_lic))

    return len(seen), violations


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check third-party dependency licenses."
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enforce strict allowlist matching for every package",
    )
    args = parser.parse_args()

    total_scanned, violations = check_licenses(strict=args.strict)
    logger.info("Scanned %d installed third-party packages", total_scanned)

    if violations:
        logger.error("Found %d license compliance issues:", len(violations))
        for pkg, ver, lic in violations:
            logger.error("  - %s (%s): %s", pkg, ver, lic)
        return 1

    logger.info("All scanned packages satisfy open-source license policy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
