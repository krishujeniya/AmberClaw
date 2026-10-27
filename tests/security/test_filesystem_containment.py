import os
from pathlib import Path
import pytest
from amberclaw.agent.tools.filesystem import _resolve_path, ReadFileTool, ReadFileArgs


def test_path_traversal_blocked(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    traversal_path = "../../etc/passwd"
    with pytest.raises(PermissionError, match="outside allowed directory"):
        _resolve_path(traversal_path, workspace=workspace)


def test_absolute_path_outside_workspace_blocked(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    outside_file = tmp_path / "secret.txt"
    outside_file.write_text("secret_data")

    with pytest.raises(PermissionError, match="outside allowed directory"):
        _resolve_path(str(outside_file), workspace=workspace)


def test_symlink_escape_blocked(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    target_file = tmp_path / "target.txt"
    target_file.write_text("sensitive_outside_content")

    symlink_file = workspace / "escaped_link.txt"
    try:
        os.symlink(target_file, symlink_file)
    except OSError:
        pytest.skip("Symlinks not supported in environment")

    # Symlink canonical resolution points to target.txt outside workspace
    with pytest.raises(PermissionError, match="outside allowed directory"):
        _resolve_path("escaped_link.txt", workspace=workspace)


@pytest.mark.asyncio
async def test_read_file_tool_blocks_traversal(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    tool = ReadFileTool(workspace=workspace)
    result = await tool.run(ReadFileArgs(path="../../etc/passwd"))

    assert "PermissionError" in result or "outside allowed directory" in result or "Error" in result


def test_valid_workspace_file_allowed(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    sub_dir = workspace / "data"
    sub_dir.mkdir()
    valid_file = sub_dir / "test.txt"
    valid_file.write_text("hello workspace")

    resolved = _resolve_path("data/test.txt", workspace=workspace)
    assert resolved == valid_file.resolve()
