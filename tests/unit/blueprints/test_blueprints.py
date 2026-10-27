"""Unit tests for AmberClaw blueprints schema, loader, validator, presets, and applier."""

from pathlib import Path

import pytest

from amberclaw.blueprints.applier import BlueprintApplier
from amberclaw.blueprints.loader import BlueprintLoader
from amberclaw.blueprints.schema import (
    AgentBlueprintConfig,
    BlueprintSchema,
    SecurityBlueprintConfig,
)
from amberclaw.blueprints.validator import BlueprintValidator


def test_blueprint_schema_defaults():
    bp = BlueprintSchema(name="custom-profile")
    assert bp.name == "custom-profile"
    assert bp.agent.model_name == "gpt-4o"
    assert bp.security.sandbox_type == "docker"
    assert bp.security.require_human_approval_for_destructive is True


def test_blueprint_loader_presets():
    loader = BlueprintLoader()
    presets = loader.list_available_presets()
    expected_presets = {"default", "developer", "minimal", "paranoid"}
    assert expected_presets.issubset(set(presets))

    # Load default preset
    bp_default = loader.load_preset("default")
    assert bp_default.name == "default"
    assert bp_default.agent.model_name == "gpt-4o"

    # Load developer preset
    bp_dev = loader.load_preset("developer")
    assert bp_dev.name == "developer"
    assert "github" in bp_dev.skills

    # Load paranoid preset
    bp_paranoid = loader.load_preset("paranoid")
    assert bp_paranoid.name == "paranoid"
    assert bp_paranoid.security.allow_network_egress is False

    # Missing preset should raise FileNotFoundError
    with pytest.raises(FileNotFoundError):
        loader.load_preset("non_existent_preset_xyz")


def test_blueprint_validator():
    validator = BlueprintValidator()

    # 1. Valid Blueprint
    valid_bp = BlueprintSchema(
        name="valid-bp",
        agent=AgentBlueprintConfig(model_name="claude-3-5-sonnet-20241022", temperature=0.3),
        security=SecurityBlueprintConfig(sandbox_type="docker"),
        skills=["summarize", "weather"],
    )
    res = validator.validate(valid_bp)
    assert res.is_valid is True
    assert len(res.errors) == 0

    # 2. Invalid sandbox type and empty name (constructed via model_construct for raw check)
    invalid_agent = AgentBlueprintConfig.model_construct(model_name="gpt-4o", temperature=2.5)
    invalid_sec = SecurityBlueprintConfig.model_construct(sandbox_type="invalid_sandbox_xyz")
    invalid_bp = BlueprintSchema.model_construct(
        name="",
        agent=invalid_agent,
        security=invalid_sec,
        skills=["summarize", "summarize"],
    )
    res_inv = validator.validate(invalid_bp)
    assert res_inv.is_valid is False
    assert any("Blueprint name cannot be empty" in e for e in res_inv.errors)
    assert any("Invalid sandbox_type" in e for e in res_inv.errors)
    assert any("Temperature" in e for e in res_inv.errors)
    assert len(res_inv.warnings) > 0  # Duplicate skill warning


def test_blueprint_applier():
    applier = BlueprintApplier()
    loader = BlueprintLoader()

    bp = loader.load_preset("developer")
    report = applier.apply(bp, target_config={"existing_key": "val"})

    assert report.success is True
    assert report.blueprint_name == "developer"
    assert report.applied_settings["existing_key"] == "val"
    assert report.applied_settings["agent"]["model_name"] == "claude-3-5-sonnet-20241022"
    assert "github" in report.applied_settings["skills"]


def test_blueprint_file_io(tmp_path: Path):
    loader = BlueprintLoader()
    yaml_text = """
name: test-file-bp
version: "2.1.0"
agent:
  model_name: "gpt-4o-mini"
  temperature: 0.4
security:
  sandbox_type: "wasm"
skills:
  - "weather"
"""
    file_path = tmp_path / "custom_bp.yaml"
    file_path.write_text(yaml_text, encoding="utf-8")

    bp = loader.load_from_file(file_path)
    assert bp.name == "test-file-bp"
    assert bp.version == "2.1.0"
    assert bp.security.sandbox_type == "wasm"
