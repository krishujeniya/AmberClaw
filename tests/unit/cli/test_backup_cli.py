"""Unit tests for AmberClaw backup and restore CLI commands."""

from pathlib import Path

from typer.testing import CliRunner

from amberclaw.cli.commands import app

runner = CliRunner()


def test_cli_backup_help():
    result = runner.invoke(app, ["backup", "--help"])
    assert result.exit_code == 0
    assert "create" in result.output
    assert "list" in result.output
    assert "drill" in result.output


def test_cli_restore_help():
    result = runner.invoke(app, ["restore", "--help"])
    assert result.exit_code == 0
    assert "run" in result.output


def test_cli_backup_workflow_create_list_drill(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True)

    # Empty list first
    list_res = runner.invoke(app, ["backup", "list", "--backup-dir", str(backup_dir)])
    assert list_res.exit_code == 0
    assert "No backup archives found" in list_res.output

    # Create backup
    create_res = runner.invoke(
        app,
        [
            "backup",
            "create",
            "--name",
            "cli_test_bak",
            "--data-dir",
            str(data_dir),
            "--backup-dir",
            str(backup_dir),
        ],
    )
    assert create_res.exit_code == 0
    assert "Backup created successfully" in create_res.output

    # List again
    list_after = runner.invoke(app, ["backup", "list", "--backup-dir", str(backup_dir)])
    assert list_after.exit_code == 0
    assert "cli_test_bak" in list_after.output

    # Run DR drill
    drill_res = runner.invoke(
        app,
        [
            "backup",
            "drill",
            "--data-dir",
            str(data_dir),
            "--backup-dir",
            str(backup_dir),
        ],
    )
    assert drill_res.exit_code == 0
    assert "DR Drill Passed" in drill_res.output
