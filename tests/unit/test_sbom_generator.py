"""Inventory identity and license claims must match their evidence."""

import tomllib
from pathlib import Path
from types import SimpleNamespace

from scripts import generate_sbom


def test_sbom_uses_actual_project_version_and_valid_document_identity():
    expected = tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]
    packages = [{"name": "Some_Package", "version": "1.0+local", "license": "MIT"}]
    cdx = generate_sbom.generate_cyclonedx(packages)
    spdx = generate_sbom.generate_spdx(packages)
    assert cdx["metadata"]["component"]["version"] == expected
    assert cdx["components"][0]["purl"] == "pkg:pypi/some-package@1.0%2Blocal"
    assert spdx["SPDXID"] == "SPDXRef-DOCUMENT"
    assert spdx["packages"][0]["licenseDeclared"] == "MIT"
    assert spdx["packages"][0]["licenseConcluded"] == "NOASSERTION"
    assert spdx["relationships"][0]["spdxElementId"] == spdx["SPDXID"]
    assert "development" in spdx["comment"]


def test_unknown_license_text_is_not_a_license_expression():
    component = {
        "name": "unknown",
        "version": "1",
        "license": "Copyright 2026, see license file for terms.",
    }
    spdx = generate_sbom.generate_spdx([component])
    assert spdx["packages"][0]["licenseDeclared"] == "NOASSERTION"
    assert (
        generate_sbom.generate_cyclonedx([component])["components"][0]["licenses"] == []
    )


def test_metadata_prefers_license_expression_and_deduplicates_normalized_names(
    monkeypatch,
):
    distributions = [
        SimpleNamespace(
            metadata={
                "Name": "Some_Package",
                "Version": "1",
                "License-Expression": "MIT",
                "License": "Full copyright text",
            }
        ),
        SimpleNamespace(
            metadata={"Name": "some-package", "Version": "1", "License": "Apache-2.0"}
        ),
    ]
    monkeypatch.setattr(
        generate_sbom.importlib.metadata, "distributions", lambda: distributions
    )
    assert generate_sbom.collect_installed_packages() == [
        {"name": "some-package", "version": "1", "license": "MIT"}
    ]
