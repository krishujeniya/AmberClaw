"""Modern metadata and missing declarations must not bypass license policy."""

from types import SimpleNamespace

from scripts import check_licenses


def test_modern_disallowed_expression_takes_precedence(monkeypatch):
    distribution = SimpleNamespace(
        version="1",
        metadata={
            "Name": "example",
            "License-Expression": "AGPL-3.0-only",
            "License": "MIT",
        },
    )
    monkeypatch.setattr(
        check_licenses.importlib.metadata, "distributions", lambda: [distribution]
    )
    count, violations = check_licenses.check_licenses()
    assert count == 1
    assert violations == [("example", "1", "AGPL-3.0-only")]


def test_strict_policy_rejects_unknown_license(monkeypatch):
    distribution = SimpleNamespace(version="1", metadata={"Name": "example"})
    monkeypatch.setattr(
        check_licenses.importlib.metadata, "distributions", lambda: [distribution]
    )
    _, violations = check_licenses.check_licenses(strict=True)
    assert violations == [("example", "1", "UNKNOWN")]


def test_permitted_declared_license_passes_strict_policy(monkeypatch):
    distribution = SimpleNamespace(
        version="1", metadata={"Name": "example", "License-Expression": "MIT"}
    )
    monkeypatch.setattr(
        check_licenses.importlib.metadata, "distributions", lambda: [distribution]
    )
    assert check_licenses.check_licenses(strict=True) == (1, [])
