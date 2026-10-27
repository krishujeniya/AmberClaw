"""Unit tests for AmberClaw database migration CLI commands."""

from pathlib import Path

from typer.testing import CliRunner

from amberclaw.cli.commands import app

runner = CliRunner()


def test_cli_db_help():
    result = runner.invoke(app, ["db", "--help"])
    assert result.exit_code == 0
    assert "Manage AmberClaw database schema migrations" in result.output
    assert "upgrade" in result.output
    assert "rollback" in result.output
    assert "current" in result.output


def test_cli_db_lifecycle(tmp_path: Path):
    db_file = tmp_path / "cli_test.db"
    db_url = f"sqlite:///{db_file}"

    # 1. Upgrade
    res_up = runner.invoke(app, ["db", "upgrade", "--db-url", db_url])
    assert res_up.exit_code == 0
    assert "Database migrated successfully" in res_up.output

    # 2. Current
    res_curr = runner.invoke(app, ["db", "current", "--db-url", db_url])
    assert res_curr.exit_code == 0
    assert "0001_initial" in res_curr.output

    # 3. Rollback
    res_down = runner.invoke(app, ["db", "rollback", "--db-url", db_url])
    assert res_down.exit_code == 0
    assert "Database rollback completed" in res_down.output
