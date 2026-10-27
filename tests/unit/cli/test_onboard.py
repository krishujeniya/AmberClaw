import pytest
from pathlib import Path
from amberclaw.cli.commands.onboard import onboard


def test_onboard_init_flow(tmp_path: Path, monkeypatch):
    test_config_dir = tmp_path / ".amberclaw"
    test_workspace_dir = tmp_path / "workspace"

    monkeypatch.setattr("amberclaw.config.loader.get_config_path", lambda: test_config_dir / "config.json")
    monkeypatch.setattr("amberclaw.config.paths.get_workspace_path", lambda: test_workspace_dir)

    onboard()

    assert (test_config_dir / "config.json").exists()
    assert test_workspace_dir.exists()
