"""Unit tests for the AmberClaw OAuth CLI command suite."""

from pathlib import Path

from typer.testing import CliRunner

import amberclaw.cli.oauth as oauth_mod
from amberclaw.cli.commands import app

runner = CliRunner()


def test_oauth_flow(tmp_path: Path, monkeypatch):
    test_token_path = tmp_path / "tokens.json"
    monkeypatch.setattr(oauth_mod, "TOKEN_STORE_PATH", test_token_path)

    # Initially empty status
    res_init = runner.invoke(app, ["oauth", "status"])
    assert res_init.exit_code == 0
    assert "No OAuth providers currently authenticated" in res_init.output

    # Login
    res_login = runner.invoke(app, ["oauth", "login", "google"])
    assert res_login.exit_code == 0
    assert "Successfully authorized google" in res_login.output

    # Status with provider
    res_status = runner.invoke(app, ["oauth", "status"])
    assert res_status.exit_code == 0
    assert "google" in res_status.output
    assert "authorized" in res_status.output

    # Token
    res_token = runner.invoke(app, ["oauth", "token", "google"])
    assert res_token.exit_code == 0
    assert "token_" in res_token.output

    # Logout
    res_logout = runner.invoke(app, ["oauth", "logout", "google"])
    assert res_logout.exit_code == 0
    assert "Logged out from google" in res_logout.output

    # Token after logout fails
    res_token_after = runner.invoke(app, ["oauth", "token", "google"])
    assert res_token_after.exit_code != 0
