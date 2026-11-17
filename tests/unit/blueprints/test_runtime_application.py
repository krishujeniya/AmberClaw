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
def test_full_presets_apply_to_config_successfully(preset):
    config = Config()
    original = config.model_dump()
    blueprint = BlueprintLoader().load_preset(preset)
    report = BlueprintApplier().apply_to_config(blueprint, config)
    assert report.success, report.errors
    assert report.applied_settings != {}
    result = Config.model_validate(report.applied_settings)

    # Verify security policy applied
    assert result.security.sandbox_type == blueprint.security.sandbox_type
    assert result.security.allow_network_egress == blueprint.security.allow_network_egress
    assert result.security.restricted_paths == blueprint.security.restricted_paths
    assert (
        result.security.require_human_approval_for_destructive
        == blueprint.security.require_human_approval_for_destructive
    )

    # Verify agent settings applied
    assert result.agents.defaults.model == blueprint.agent.model_name
    assert result.agents.defaults.temperature == blueprint.agent.temperature
    assert result.agents.defaults.max_tool_iterations == blueprint.agent.max_turns
    assert result.agents.defaults.system_prompt == blueprint.agent.system_prompt
    assert (
        result.agents.defaults.memory_nudge_enabled
        == blueprint.agent.memory_nudge_enabled
    )
    assert result.skills == blueprint.skills

    # Verify input was not mutated
    assert config.model_dump() == original


def test_explicit_unsupported_settings_are_not_silently_discarded():
    blueprint = BlueprintSchema.model_validate(
        {"name": "unsupported", "security": {"sandbox_type": "quantum_hypervisor"}}
    )
    report = BlueprintApplier().apply_to_config(blueprint, Config())
    assert not report.success
    assert any("security.sandbox_type" in error for error in report.errors)
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


def test_cli_checks_capabilities_before_loading_config_or_migrating_secrets(tmp_path):
    invalid_file = tmp_path / "invalid.yaml"
    invalid_file.write_text(
        "name: invalid-capabilities\nsecurity:\n  sandbox_type: invalid_sandbox_hypervisor\n",
        encoding="utf-8",
    )
    with (
        patch("amberclaw.cli.commands.blueprint.load_config") as load,
        patch("amberclaw.cli.commands.blueprint.save_config") as save,
    ):
        result = CliRunner().invoke(app, ["blueprint", "apply", str(invalid_file)])
    assert result.exit_code != 0
    assert "security.sandbox_type" in result.output
    load.assert_not_called()
    save.assert_not_called()


@pytest.mark.asyncio
async def test_runtime_enforces_blueprint_restricted_paths(tmp_path):
    from amberclaw.agent.tools.filesystem import ReadFileArgs, ReadFileTool, WriteFileArgs, WriteFileTool
    from amberclaw.agent.tools.shell import ExecArgs, ExecTool
    from amberclaw.config.schema import settings

    secret_dir = tmp_path / "protected_secrets"
    secret_dir.mkdir()
    secret_file = secret_dir / "key.txt"
    secret_file.write_text("secret_data", encoding="utf-8")

    # Configure restricted paths
    original_restricted = settings.security.restricted_paths
    try:
        settings.security.restricted_paths = [str(secret_dir)]

        # 1. ReadFileTool blocks access
        read_tool = ReadFileTool(workspace=tmp_path)
        read_res = await read_tool.run(ReadFileArgs(path=str(secret_file)))
        assert "forbidden by security policy" in read_res

        # 2. WriteFileTool blocks access
        write_tool = WriteFileTool(workspace=tmp_path)
        write_res = await write_tool.run(WriteFileArgs(path=str(secret_file), content="new"))
        assert "forbidden by security policy" in write_res

        # 3. ExecTool blocks access
        exec_tool = ExecTool(working_dir=str(tmp_path), restrict_to_workspace=False)
        exec_res = await exec_tool.run(ExecArgs(command=f"cat {secret_file}"))
        assert "access to restricted path" in exec_res
    finally:
        settings.security.restricted_paths = original_restricted


@pytest.mark.asyncio
async def test_runtime_enforces_blueprint_network_egress():
    from amberclaw.agent.tools.shell import ExecArgs, ExecTool
    from amberclaw.agent.tools.web import WebFetchArgs, WebFetchTool, WebSearchArgs, WebSearchTool
    from amberclaw.config.schema import settings

    original_egress = settings.security.allow_network_egress
    try:
        settings.security.allow_network_egress = False

        # 1. WebSearchTool blocks
        search_tool = WebSearchTool()
        search_res = await search_tool.run(WebSearchArgs(query="amberclaw security"))
        assert "Network egress is disabled by security policy" in search_res

        # 2. WebFetchTool blocks
        fetch_tool = WebFetchTool()
        fetch_res = await fetch_tool.run(WebFetchArgs(url="https://example.com"))
        assert "Network egress is disabled by security policy" in fetch_res

        # 3. ExecTool network commands blocked
        exec_tool = ExecTool()
        exec_res = await exec_tool.run(ExecArgs(command="curl https://example.com"))
        assert "network egress is disabled" in exec_res
    finally:
        settings.security.allow_network_egress = original_egress


@pytest.mark.asyncio
async def test_runtime_enforces_blueprint_destructive_approval(tmp_path):
    from amberclaw.agent.tools.filesystem import WriteFileTool
    from amberclaw.agent.tools.registry import ToolRegistry
    from amberclaw.config.schema import settings
    from amberclaw.security.approval import ToolApprovalManager

    approval_mgr = ToolApprovalManager.get_instance()
    approval_mgr.clear()

    reg = ToolRegistry()
    reg.register(WriteFileTool(workspace=tmp_path))

    original_approval = settings.security.require_human_approval_for_destructive
    target_file = tmp_path / "approved.txt"
    try:
        settings.security.require_human_approval_for_destructive = True

        # First call without approval generates ticket
        res = await reg.execute(
            "write_file",
            {"path": str(target_file), "content": "approved content"},
        )
        assert "requires human approval" in res
        assert "ticket:" in res

        # Extract ticket id
        ticket_id = res.split("ticket: ")[1].split(")")[0]

        # Resolve ticket as approved
        assert approval_mgr.resolve_ticket(ticket_id, approved=True)

        # Retry call with approved ticket succeeds
        approved_res = await reg.execute(
            "write_file",
            {"path": str(target_file), "content": "approved content", "approval_ticket_id": ticket_id},
        )
        assert "Successfully wrote" in approved_res
        assert target_file.read_text(encoding="utf-8") == "approved content"

        # When require_human_approval_for_destructive is False (e.g. developer preset), no ticket is required
        settings.security.require_human_approval_for_destructive = False
        target_file_dev = tmp_path / "dev.txt"
        dev_res = await reg.execute(
            "write_file",
            {"path": str(target_file_dev), "content": "direct write"},
        )
        assert "Successfully wrote" in dev_res
        assert target_file_dev.read_text(encoding="utf-8") == "direct write"
    finally:
        settings.security.require_human_approval_for_destructive = original_approval
        approval_mgr.clear()


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
