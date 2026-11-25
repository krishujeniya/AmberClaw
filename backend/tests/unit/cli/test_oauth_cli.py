"""Offline CLI lifecycle over real-format credentials from a mocked OAuth exchange."""

import time
from pathlib import Path

from oauth_cli_kit import OAuthToken
from typer.testing import CliRunner

import amberclaw.cli.oauth as oauth_mod
from amberclaw.cli.commands import app

PRIVATE_TOKEN_MODE = 0o600
runner = CliRunner()


def test_oauth_flow(tmp_path: Path, monkeypatch):
    token_path = tmp_path / "tokens.json"
    monkeypatch.setattr(oauth_mod, "TOKEN_STORE_PATH", token_path)
    exchanges = []

    def exchange(**kwargs):
        exchanges.append(kwargs["provider"])
        token = OAuthToken(
            access="fixture-access",
            refresh="fixture-refresh",
            expires=int(time.time() * 1000) + 3600000,
            account_id="fixture-account",
        )
        kwargs["storage"].save(token)
        return token

    monkeypatch.setattr(oauth_mod, "login_oauth_interactive", exchange)
    initial = runner.invoke(app, ["oauth", "status"])
    assert initial.exit_code == 0
    assert "No OAuth providers currently authenticated" in initial.output
    login = runner.invoke(app, ["oauth", "login", "openai-codex"])
    assert login.exit_code == 0, login.exception
    assert exchanges == [oauth_mod.OPENAI_CODEX_PROVIDER]
    assert token_path.is_file()
    assert token_path.stat().st_mode & 0o777 == PRIVATE_TOKEN_MODE
    status = runner.invoke(app, ["oauth", "status"])
    assert status.exit_code == 0
    assert "openai-codex" in status.output
    assert "authorized" in status.output
    token = runner.invoke(app, ["oauth", "token", "codex"])
    assert token.exit_code == 0
    assert "fixture-access" in token.output
    logout = runner.invoke(app, ["oauth", "logout", "codex"])
    assert logout.exit_code == 0
    assert not token_path.exists()
    assert runner.invoke(app, ["oauth", "token", "codex"]).exit_code != 0


def test_unsupported_oauth_does_not_create_credentials(tmp_path, monkeypatch):
    path = tmp_path / "tokens.json"
    monkeypatch.setattr(oauth_mod, "TOKEN_STORE_PATH", path)
    result = runner.invoke(app, ["oauth", "login", "google"])
    assert result.exit_code != 0
    assert "Successfully authorized" not in result.output
    assert not path.exists()
