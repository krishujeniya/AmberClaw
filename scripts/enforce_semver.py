#!/usr/bin/env python3
# ruff: noqa: T201
"""Enforces Semantic Versioning 2.0.0 rules for AmberClaw releases.

Validates that pyproject.toml version strings strictly conform to SemVer specifications.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SEMVER_REGEX = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


def validate_semver(version: str) -> bool:
    """Validates that a version string strictly matches SemVer 2.0.0."""
    cleaned = version.strip()
    if cleaned.startswith("v"):
        cleaned = cleaned[1:]
    return bool(SEMVER_REGEX.match(cleaned))


def get_project_version(pyproject_path: Path | str = "pyproject.toml") -> str:
    """Reads current project version from pyproject.toml."""
    content = Path(pyproject_path).read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    if not match:
        raise ValueError("Could not find version field in pyproject.toml")
    return match.group(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce Semantic Versioning 2.0.0.")
    parser.add_argument("--version", help="Specific version string to validate")
    args = parser.parse_args()

    version = args.version or get_project_version()
    if not validate_semver(version):
        print(
            f"ERROR: Version '{version}' is not a valid SemVer 2.0.0 string.",
            file=sys.stderr,
        )
        return 1

    print(f"SUCCESS: Version '{version}' is a valid SemVer 2.0.0 release.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
