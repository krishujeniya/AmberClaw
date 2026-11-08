"""Offline regression checks for CLI command wiring and credential boundaries."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from amberclaw.cli import oauth
from amberclaw.cli.commands import app
from amberclaw.config import loader
from amberclaw.config.schema import Config

runner = CliRunner()


@pytest.mark.parametrize("name", ["google", "github", "unknown"])
def test_oauth_unsupported_never_creates_credentials(name, tmp_path, monkeypatch):
    path = tmp_path / "tokens.json"
    monkeypatch.setattr(oauth, "TOKEN_STORE_PATH", path)
    result = runner.invoke(app, ["oauth", "login", name])
    assert result.exit_code != 0
    assert not path.exists()
    assert "Successfully authorized" not in result.output
    assert "Listening for callback" not in result.output


@pytest.mark.parametrize("payload", [[], "text", None, {"provider": []}])
def test_oauth_store_rejects_wrong_shape(payload, tmp_path, monkeypatch):
    path = tmp_path / "tokens.json"
    path.write_text(json.dumps(payload))
    monkeypatch.setattr(oauth, "TOKEN_STORE_PATH", path)
    assert oauth._load_token_store() == {}


@pytest.mark.parametrize("command", ["council", "mythos"])
def test_reasoning_commands_use_actual_tool_contract(command):
    tool_module = f"amberclaw.agent.tools.{command}"
    tool_name = f"{command.title()}Tool"
    with (
        patch("amberclaw.config.loader.load_runtime_config", return_value=Config()),
        patch("amberclaw.providers.factory.make_provider", return_value=object()),
        patch(f"{tool_module}.{tool_name}", autospec=True) as tool_class,
        patch("amberclaw.cli.commands.utils._print_agent_response") as output,
    ):
        tool_class.return_value.run = AsyncMock(return_value="offline result")
        result = runner.invoke(app, [command, "a question"])
    assert result.exit_code == 0, result.exception
    tool_class.assert_called_once()
    assert "workspace" not in tool_class.call_args.kwargs
    tool_class.return_value.run.assert_awaited_once()
    args = tool_class.return_value.run.await_args.args[0]
    assert args.query == "a question"
    output.assert_called_once_with("offline result", render_markdown=True)


def test_config_validation_does_not_echo_secret(tmp_path, capsys):
    path = tmp_path / "config.json"
    private_value = "fixture-sensitive-value"
    path.write_text(json.dumps({"agents": {"defaults": {"max_tokens": private_value}}}))
    loader.load_config(path)
    captured = capsys.readouterr()
    assert private_value not in captured.out + captured.err


def test_blueprint_rejects_unimplemented_preset_without_saving(tmp_path):
    with (
        patch("amberclaw.cli.commands.blueprint.load_config", return_value=Config()),
        patch(
            "amberclaw.cli.commands.blueprint.get_config_path",
            return_value=tmp_path / "config.json",
        ),
        patch("amberclaw.cli.commands.blueprint.save_config") as save,
    ):
        result = runner.invoke(app, ["blueprint", "apply", "developer"])
    assert result.exit_code != 0
    save.assert_not_called()
    assert "security.sandbox_type" in result.output
    assert "agent.system_prompt" in result.output


def test_web_status_uses_public_health():
    with patch(
        "amberclaw.cli.commands.web.httpx.get",
        return_value=SimpleNamespace(status_code=200),
    ) as get:
        result = runner.invoke(app, ["web", "status"])
    assert result.exit_code == 0
    assert get.call_args.args[0] == "http://127.0.0.1:8080/health"


def test_one_shot_stops_and_closes_after_processing_failure(tmp_path):
    calls = []
    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path)
    loop = MagicMock()
    loop.process_direct = AsyncMock(side_effect=RuntimeError("offline failure"))
    loop.stop.side_effect = lambda: calls.append("stop")
    loop.close_mcp = AsyncMock(side_effect=lambda: calls.append("close"))
    with (
        patch("amberclaw.config.loader.load_runtime_config", return_value=cfg),
        patch("amberclaw.providers.factory.make_provider", return_value=object()),
        patch("amberclaw.utils.helpers.sync_workspace_templates"),
        patch("amberclaw.config.paths.get_cron_dir", return_value=tmp_path),
        patch("amberclaw.cron.service.CronService"),
        patch("amberclaw.agent.loop.AgentLoop", return_value=loop),
    ):
        result = runner.invoke(app, ["agent", "--message", "hello"])
    assert isinstance(result.exception, RuntimeError)
    assert calls == ["stop", "close"]
