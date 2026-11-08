"""Canonical blueprint application must preserve configuration and fail closed."""

import secrets
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from amberclaw.blueprints.applier import BlueprintApplicationReport, BlueprintApplier
from amberclaw.blueprints.loader import BlueprintLoader
from amberclaw.blueprints.schema import BlueprintSchema
from amberclaw.cli.commands import app
from amberclaw.config.schema import Config


def test_supported_settings_map_to_consumed_runtime_fields_without_mutation():
    config = Config()
    config.providers.openai.api_key = "fixture-preserved-key"
    config.channels.telegram.token = secrets.token_urlsafe(12)
    config.channels.discord.enabled = True
    config.channels.send_progress = False
    original = config.model_dump()
    blueprint = BlueprintSchema.model_validate(
        {
            "name": "supported-patch",
            "agent": {
                "model_name": "openai/gpt-4o-mini",
                "temperature": 0.4,
                "max_turns": 23,
            },
            "channels": ["telegram"],
        }
    )

    report = BlueprintApplier().apply_to_config(blueprint, config)

    assert report.success, report.errors
    result = Config.model_validate(report.applied_settings)
    expected = config.model_copy(deep=True)
    expected.agents.defaults.model = blueprint.agent.model_name
    expected.agents.defaults.temperature = blueprint.agent.temperature
    expected.agents.defaults.max_tool_iterations = blueprint.agent.max_turns
    expected.channels.telegram.enabled = True
    expected.channels.discord.enabled = False
    assert result.model_dump() == expected.model_dump()
    assert config.model_dump() == original


def test_omitted_settings_leave_existing_configuration_unchanged():
    config = Config()
    config.agents.defaults.model = "existing/model"
    config.channels.slack.enabled = True
    report = BlueprintApplier().apply_to_config(BlueprintSchema(name="no-op"), config)
    assert report.success, report.errors
    assert report.applied_settings == config.model_dump()


def test_model_only_patch_preserves_other_agent_settings():
    config = Config()
    config.agents.defaults.temperature = 0.25
    config.agents.defaults.max_tool_iterations = 17
    blueprint = BlueprintSchema.model_validate(
        {"name": "model-only", "agent": {"model_name": "new/model"}}
    )
    report = BlueprintApplier().apply_to_config(blueprint, config)
    expected = config.model_copy(deep=True)
    expected.agents.defaults.model = blueprint.agent.model_name
    assert report.success, report.errors
    assert report.applied_settings == expected.model_dump()


@pytest.mark.parametrize("preset", ["default", "developer", "minimal", "paranoid"])
def test_full_presets_reject_unimplemented_policy_without_partial_application(preset):
    config = Config()
    original = config.model_dump()
    blueprint = BlueprintLoader().load_preset(preset)
    report = BlueprintApplier().apply_to_config(blueprint, config)
    assert not report.success
    assert report.applied_settings == {}
    for field in [
        "agent.system_prompt",
        "agent.memory_nudge_enabled",
        "security.sandbox_type",
        "security.allow_network_egress",
        "security.restricted_paths",
        "security.require_human_approval_for_destructive",
        "skills",
    ]:
        assert any(field in error for error in report.errors), field
    assert config.model_dump() == original


@pytest.mark.parametrize(
    "settings",
    [
        {"agent": {"system_prompt": "custom prompt"}},
        {"agent": {"memory_nudge_enabled": False}},
        {"skills": []},
        {"security": {"allow_network_egress": False}},
    ],
)
def test_explicit_unsupported_settings_are_not_silently_discarded(settings):
    blueprint = BlueprintSchema.model_validate({"name": "unsupported", **settings})
    report = BlueprintApplier().apply_to_config(blueprint, Config())
    assert not report.success
    assert report.errors
    assert report.applied_settings == {}


def test_unknown_channel_is_reported_without_mutating_input():
    config = Config()
    original = config.model_dump()
    blueprint = BlueprintSchema(
        name="invalid-channel", channels=["telegram", "unknown-channel"]
    )
    report = BlueprintApplier().apply_to_config(blueprint, config)
    assert not report.success
    assert any(
        "channels" in error and "unknown-channel" in error for error in report.errors
    )
    assert report.applied_settings == {}
    assert config.model_dump() == original


def test_explicit_empty_channels_disables_channels_and_preserves_credentials():
    config = Config()
    config.channels.telegram.enabled = True
    config.channels.telegram.token = secrets.token_urlsafe(12)
    report = BlueprintApplier().apply_to_config(
        BlueprintSchema(name="offline", channels=[]), config
    )
    assert report.success, report.errors
    result = Config.model_validate(report.applied_settings)
    assert not result.channels.telegram.enabled
    assert result.channels.telegram.token == config.channels.telegram.token
    assert config.channels.telegram.enabled


def test_cli_persists_only_canonical_supported_patch(tmp_path):
    temperature = 0.4
    iterations = 23
    blueprint = tmp_path / "supported.yaml"
    blueprint.write_text(
        "name: supported\nagent:\n  model_name: openai/gpt-4o-mini\n  temperature: 0.4\n  max_turns: 23\nchannels: [telegram]\n",
        encoding="utf-8",
    )
    config = Config()
    config.providers.openai.api_key = "fixture-preserved-key"
    original = config.model_dump()
    with (
        patch("amberclaw.cli.commands.blueprint.load_config", return_value=config),
        patch(
            "amberclaw.cli.commands.blueprint.get_config_path",
            return_value=tmp_path / "config.json",
        ),
        patch("amberclaw.cli.commands.blueprint.save_config") as save,
    ):
        result = CliRunner().invoke(app, ["blueprint", "apply", str(blueprint)])
    assert result.exit_code == 0, result.exception
    saved, path = save.call_args.args
    assert isinstance(saved, Config)
    assert saved.agents.defaults.model == "openai/gpt-4o-mini"
    assert saved.agents.defaults.temperature == temperature
    assert saved.agents.defaults.max_tool_iterations == iterations
    assert saved.channels.telegram.enabled
    assert saved.providers.openai.api_key == config.providers.openai.api_key
    assert path == tmp_path / "config.json"
    assert config.model_dump() == original


def test_cli_checks_capabilities_before_loading_config_or_migrating_secrets():
    with (
        patch("amberclaw.cli.commands.blueprint.load_config") as load,
        patch("amberclaw.cli.commands.blueprint.save_config") as save,
    ):
        result = CliRunner().invoke(app, ["blueprint", "apply", "paranoid"])
    assert result.exit_code != 0
    assert "security.allow_network_egress" in result.output
    load.assert_not_called()
    save.assert_not_called()


def test_cli_rejects_invalid_application_report_before_saving(tmp_path):
    blueprint = tmp_path / "supported.yaml"
    blueprint.write_text("name: supported\nchannels: []\n", encoding="utf-8")
    report = BlueprintApplicationReport(
        blueprint_name="supported",
        success=True,
        applied_settings={"channels": ["telegram"]},
    )
    with (
        patch("amberclaw.cli.commands.blueprint.load_config", return_value=Config()),
        patch(
            "amberclaw.cli.commands.blueprint.BlueprintApplier.apply_to_config",
            return_value=report,
        ),
        patch("amberclaw.cli.commands.blueprint.save_config") as save,
    ):
        result = CliRunner().invoke(app, ["blueprint", "apply", str(blueprint)])
    assert result.exit_code != 0
    assert "nothing was saved" in result.output
    save.assert_not_called()


def test_semantically_invalid_blueprint_returns_errors_without_application():
    report = BlueprintApplier().apply_to_config(BlueprintSchema(name=" "), Config())
    assert not report.success
    assert "Blueprint name cannot be empty." in report.errors
    assert report.applied_settings == {}
