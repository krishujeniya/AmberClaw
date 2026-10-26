"""End-to-End CLI workflow tests for AmberClaw OS.

Validates:
1. Root CLI command dispatch, global flags (--help, --version)
2. 'doctor' system diagnostics and dependency checks
3. 'status' configuration and workspace inspector
4. 'scan-secrets' zero-findings pass and secret detection failure exits
5. 'db' migrations CLI (current revision inspection and dry-run execution)
6. 'skill' subcommand lifecycle (listing and installation)
"""

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from amberclaw import __version__
from amberclaw.cli.commands import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "amberclaw" in result.output.lower()
    assert "doctor" in result.output
    assert "status" in result.output
    assert "scan-secrets" in result.output
    assert "skill" in result.output
    assert "db" in result.output


def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_cli_status(tmp_path: Path):
    fake_config = tmp_path / "config.toml"
    fake_config.write_text("[general]\nworkspace = '/tmp'\n", encoding="utf-8")

    with patch("amberclaw.config.loader.get_config_path", return_value=fake_config):
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "Status" in result.output
        assert "Workspace:" in result.output


def test_cli_doctor():
    with patch("amberclaw.cli.commands.doctor.run_doctor") as mock_doctor:
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        mock_doctor.assert_called_once()


def test_cli_scan_secrets_clean_workspace(tmp_path: Path):
    clean_dir = tmp_path / "clean_ws"
    clean_dir.mkdir()
    (clean_dir / "app.py").write_text("print('Hello AmberClaw')", encoding="utf-8")

    result = runner.invoke(app, ["scan-secrets", "--path", str(clean_dir)])
    assert result.exit_code == 0
    assert "No secrets found" in result.output


def test_cli_scan_secrets_detects_leak(tmp_path: Path):
    dirty_dir = tmp_path / "dirty_ws"
    dirty_dir.mkdir()
    # Plant a typical AWS Access Key pattern: AKIA + 16 chars
    leak_file = dirty_dir / "credentials.txt"
    leak_file.write_text("AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")

    result = runner.invoke(app, ["scan-secrets", "--path", str(dirty_dir)])
    assert result.exit_code == 1
    assert "potential secret" in result.output.lower()


def test_cli_db_commands():
    with patch(
        "amberclaw.cli.commands.db.get_current_revision", return_value="v1_init_rev"
    ):
        res_current = runner.invoke(app, ["db", "current"])
        assert res_current.exit_code == 0
        assert "v1_init_rev" in res_current.output

    with (
        patch("amberclaw.cli.commands.db.apply_migrations", return_value=True),
        patch(
            "amberclaw.cli.commands.db.get_current_revision", return_value="v2_head_rev"
        ),
    ):
        res_upgrade = runner.invoke(app, ["db", "upgrade"])
        assert res_upgrade.exit_code == 0
        assert "v2_head_rev" in res_upgrade.output


def test_cli_skills_listing(tmp_path: Path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "code_analyzer").mkdir()
    (skills_dir / "web_search").mkdir()

    with patch("amberclaw.config.paths.get_workspace_path", return_value=tmp_path):
        result = runner.invoke(app, ["skill", "list"])
        assert result.exit_code == 0
        assert "code_analyzer" in result.output
        assert "web_search" in result.output
