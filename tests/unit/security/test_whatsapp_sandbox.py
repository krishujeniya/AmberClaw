"""Tests for WhatsApp bridge bubblewrap sandboxing and security controls."""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from amberclaw.config.schema import Config
from amberclaw.security.whatsapp_sandbox import (
    build_bwrap_args,
    get_whatsapp_bridge_paths,
    is_bwrap_available,
    spawn_isolated_whatsapp_bridge,
)


def test_is_bwrap_available() -> None:
    with patch("shutil.which") as mock_which:
        mock_which.return_value = "/usr/bin/bwrap"
        assert is_bwrap_available() is True

        mock_which.return_value = None
        assert is_bwrap_available() is False


def test_get_whatsapp_bridge_paths() -> None:
    bridge_dir, auth_dir, media_dir = get_whatsapp_bridge_paths()
    assert isinstance(bridge_dir, Path)
    assert isinstance(auth_dir, Path)
    assert isinstance(media_dir, Path)
    assert bridge_dir.exists()
    assert auth_dir.exists()
    assert media_dir.exists()


def test_build_bwrap_args_success() -> None:
    bridge_dir = Path("/tmp/amberclaw/bridge")  # noqa: S108
    auth_dir = Path("/tmp/amberclaw/auth")      # noqa: S108
    media_dir = Path("/tmp/amberclaw/media")    # noqa: S108

    with patch("amberclaw.security.whatsapp_sandbox.is_bwrap_available", return_value=True), \
         patch("shutil.which", return_value="/usr/bin/node"), \
         patch("os.path.exists", return_value=True):

        args = build_bwrap_args(
            bridge_dir,
            auth_dir,
            media_dir,
        )

        assert args is not None
        assert "bwrap" in args
        assert "--unshare-user" in args
        assert "--unshare-ipc" in args
        assert "--unshare-pid" in args
        assert "--unshare-uts" in args
        assert "--die-with-parent" in args
        assert "--cap-drop" in args
        assert "ALL" in args

        # Assert read-only binds for system paths exist
        assert "/usr" in args
        assert "/lib" in args
        assert "/etc" in args

        # Assert writable binds exist
        assert str(bridge_dir) in args
        assert str(auth_dir) in args
        assert str(media_dir) in args
        assert "--chdir" in args


def test_build_bwrap_args_not_available() -> None:
    bridge_dir = Path("/tmp/amberclaw/bridge")  # noqa: S108
    auth_dir = Path("/tmp/amberclaw/auth")      # noqa: S108
    media_dir = Path("/tmp/amberclaw/media")    # noqa: S108

    with patch("amberclaw.security.whatsapp_sandbox.is_bwrap_available", return_value=False):
        args = build_bwrap_args(
            bridge_dir,
            auth_dir,
            media_dir,
        )
        assert args is None


@pytest.mark.asyncio
async def test_spawn_isolated_whatsapp_bridge_fallback() -> None:
    config = Config()
    config.channels.whatsapp.enabled = True
    config.channels.whatsapp.bridge_token = "test-token"  # noqa: S105
    config.channels.whatsapp.bridge_port = 3005

    # Mock the index.js check and subprocess exec
    with patch("amberclaw.security.whatsapp_sandbox.is_bwrap_available", return_value=False), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("shutil.which", return_value="/usr/bin/node"), \
         patch("asyncio.create_subprocess_exec") as mock_exec:

        mock_proc = MagicMock()
        mock_exec.return_value = mock_proc

        proc = await spawn_isolated_whatsapp_bridge(config)

        assert proc == mock_proc
        mock_exec.assert_called_once()
        called_args = mock_exec.call_args[0]
        assert called_args[0] == "/usr/bin/node"
        assert called_args[1] == "dist/index.js"


def test_path_traversal_prevention_logic() -> None:
    # This simulates the logic implemented in Node.js bridge to sanitize filenames.
    # It must strip all directory traversal components.

    def sanitize_filename(filename: str) -> str:
        # Normalize backslashes to forward slashes first
        normalized = filename.replace("\\", "/")
        # 1. Extract basename using Path
        base = Path(normalized).name
        # 2. Strip dangerous characters (non-alphanumeric, dots and hyphens only allowed)
        safe = re.sub(r"[^a-zA-Z0-9.-]", "_", base)
        # 3. Handle dot-only fallbacks
        if safe in ("", ".", ".."):
            return "document.bin"
        return safe

    # Test cases matching malicious inputs
    assert sanitize_filename("../../../../etc/passwd") == "passwd"
    assert sanitize_filename("..\\..\\..\\..\\windows\\system32\\cmd.exe") == "cmd.exe"
    assert sanitize_filename("normal-document.pdf") == "normal-document.pdf"
    assert sanitize_filename("../../info..txt") == "info..txt"
    assert sanitize_filename("..") == "document.bin"
    assert sanitize_filename(".") == "document.bin"
