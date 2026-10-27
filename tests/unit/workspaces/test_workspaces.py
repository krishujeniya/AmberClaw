"""Unit tests for AmberClaw workspaces containment, runtime, GitOps, and manager."""

import sys
from pathlib import Path

import pytest

from amberclaw.workspaces.git_ops import GitOps
from amberclaw.workspaces.manager import WorkspaceManager
from amberclaw.workspaces.runtime import WorkspaceRuntime
from amberclaw.workspaces.workspace import WorkspaceContext


def test_workspace_context_containment(tmp_path: Path):
    root = tmp_path / "sandbox"
    root.mkdir()

    ctx = WorkspaceContext(
        workspace_id="ws-1",
        name="Test Sandbox",
        root_path=root,
        is_isolated=True,
    )

    # Valid inside path
    safe_path = ctx.resolve_path("src/main.py")
    assert safe_path == (root / "src/main.py").resolve()

    # Directory traversal attack should raise PermissionError
    with pytest.raises(PermissionError):
        ctx.resolve_path("../../../etc/passwd")

    # Ensure directory
    sub = ctx.ensure_directory("data/logs")
    assert sub.is_dir()


def test_workspace_runtime_io_and_commands(tmp_path: Path):
    root = tmp_path / "sandbox"
    root.mkdir()

    ctx = WorkspaceContext(
        workspace_id="ws-2",
        name="Runtime Sandbox",
        root_path=root,
        env_vars={"APP_ENV": "testing"},
    )
    runtime = WorkspaceRuntime(ctx)

    # Write file
    file_path = runtime.write_file("config.json", '{"debug": true}')
    assert file_path.exists()

    # Read file
    content = runtime.read_file("config.json")
    assert '{"debug": true}' in content

    # List files
    files = runtime.list_files()
    assert "config.json" in files

    # Run command
    res = runtime.run_command([sys.executable, "-c", "import os; print(os.getenv('APP_ENV'))"])
    assert res.exit_code == 0
    assert "testing" in res.stdout.strip()


def test_workspace_git_ops(tmp_path: Path):
    root = tmp_path / "git_sandbox"
    root.mkdir()

    ctx = WorkspaceContext(
        workspace_id="ws-git",
        name="Git Sandbox",
        root_path=root,
    )
    git_ops = GitOps(ctx)

    # Initially not git repo
    assert git_ops.is_git_repo() is False

    # Init repo
    assert git_ops.init_repository() is True
    assert git_ops.is_git_repo() is True

    # Add file and commit
    (root / "README.md").write_text("# Hello World", encoding="utf-8")
    assert git_ops.stage_and_commit("Initial commit") is True

    # Check status
    status = git_ops.get_status_short()
    assert status == ""  # Clean working tree


def test_workspace_manager_lifecycle(tmp_path: Path):
    manager = WorkspaceManager(base_storage_dir=tmp_path / "workspaces")

    # Create workspace
    ctx = manager.create_workspace(
        workspace_id="ws-app",
        name="App Project",
    )
    assert ctx.root_path.exists()
    assert len(manager.list_workspaces()) == 1

    # Get runtime
    runtime = manager.get_runtime("ws-app")
    assert runtime is not None
    runtime.write_file("app.py", "print('hello')")
    assert (ctx.root_path / "app.py").exists()

    # Delete workspace
    assert manager.delete_workspace("ws-app", remove_files=True) is True
    assert len(manager.list_workspaces()) == 0
    assert not ctx.root_path.exists()
