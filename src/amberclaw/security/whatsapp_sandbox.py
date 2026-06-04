"""Bubblewrap (bwrap) sandboxing for isolated execution of the WhatsApp Node.js bridge."""

import asyncio
import logging
import os
import shutil
from pathlib import Path

from amberclaw.config.paths import (
    get_bridge_install_dir,
    get_media_dir,
    get_runtime_subdir,
)
from amberclaw.config.schema import Config

logger = logging.getLogger(__name__)


def is_bwrap_available() -> bool:
    """Check if bubblewrap (bwrap) is installed on the system."""
    return shutil.which("bwrap") is not None


def get_whatsapp_bridge_paths() -> tuple[Path, Path, Path]:
    """Get the bridge directory, auth directory, and media directory.

    Ensures they exist on the host filesystem.
    """
    bridge_dir = get_bridge_install_dir()
    auth_dir = get_runtime_subdir("whatsapp-auth")
    media_dir = get_media_dir("whatsapp")

    bridge_dir.mkdir(parents=True, exist_ok=True)
    auth_dir.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)

    return bridge_dir.resolve(), auth_dir.resolve(), media_dir.resolve()


def build_bwrap_args(
    bridge_dir: Path, auth_dir: Path, media_dir: Path
) -> list[str] | None:
    """Build the command-line arguments to run the WhatsApp bridge inside bubblewrap.

    Returns None if bwrap or node is not available.
    """
    if not is_bwrap_available():
        return None

    node_bin = shutil.which("node")
    if not node_bin:
        logger.warning("Node.js binary not found. Cannot construct bubblewrap sandbox.")
        return None

    # Base bubblewrap sandbox arguments
    # We do NOT pass --unshare-net because the bridge must connect to WhatsApp Web
    args = [
        "bwrap",
        "--unshare-user",
        "--unshare-ipc",
        "--unshare-pid",
        "--unshare-uts",
        "--die-with-parent",
        "--cap-drop", "ALL",
    ]

    # Bind system paths required for node execution and TLS validation
    system_paths = ["/usr", "/lib", "/lib64", "/bin", "/sbin", "/etc"]
    for path in system_paths:
        if Path(path).exists():
            args.extend(["--ro-bind", path, path])

    # Bind node installation prefix in case it's in a non-standard path (e.g. NVM, /opt, etc.)
    node_bin_resolved = Path(node_bin).resolve()
    # If node is installed in a user home folder or custom path, mount its directory
    node_prefix = node_bin_resolved.parent.parent
    if node_prefix not in [Path("/usr"), Path("/"), Path("/usr/local")] and node_prefix.exists():
        args.extend(["--ro-bind", str(node_prefix), str(node_prefix)])

    # Setup proc, dev, and writable tmpfs
    args.extend(["--proc", "/proc"])
    args.extend(["--dev", "/dev"])
    args.extend(["--tmpfs", "/tmp"])  # noqa: S108
    args.extend(["--tmpfs", "/run"])

    # Bind application data directories as read-write
    args.extend(["--bind", str(bridge_dir), str(bridge_dir)])
    args.extend(["--bind", str(auth_dir), str(auth_dir)])
    args.extend(["--bind", str(media_dir), str(media_dir)])

    # Set working directory and run node directly
    args.extend(["--chdir", str(bridge_dir)])
    args.extend([str(node_bin_resolved), "dist/index.js"])

    return args


async def spawn_isolated_whatsapp_bridge(
    config: Config,
    stdout: int = asyncio.subprocess.PIPE,
    stderr: int = asyncio.subprocess.PIPE,
) -> asyncio.subprocess.Process:
    """Spawns the Node.js WhatsApp bridge subprocess in a sandbox.

    Attempts to use bubblewrap sandbox isolation if available. Falls back
    to an un-sandboxed subprocess with a security warning if bubblewrap is not installed.
    """
    bridge_dir, auth_dir, media_dir = get_whatsapp_bridge_paths()
    bridge_port = config.channels.whatsapp.bridge_port
    bridge_token = config.channels.whatsapp.bridge_token

    env = {
        **os.environ,
        "BRIDGE_PORT": str(bridge_port),
        "AUTH_DIR": str(auth_dir),
        "BRIDGE_TOKEN": bridge_token,
    }

    # Verify that index.js exists (has been built)
    if not (bridge_dir / "dist" / "index.js").exists():
        raise FileNotFoundError(
            f"WhatsApp bridge is not built. Please run 'amberclaw channels install' first. Path: {bridge_dir / 'dist' / 'index.js'}"
        )

    bwrap_args = build_bwrap_args(bridge_dir, auth_dir, media_dir)

    if bwrap_args:
        logger.info(
            "Spawning WhatsApp bridge in secure bubblewrap sandbox (port=%d).",
            bridge_port,
        )
        logger.debug("bwrap command: %s", " ".join(bwrap_args))
        # Spawn isolated process
        proc = await asyncio.create_subprocess_exec(
            *bwrap_args,
            env=env,
            stdout=stdout,
            stderr=stderr,
        )
    else:
        logger.warning(
            "⚠️ Bubblewrap sandbox is not available. Spawning WhatsApp bridge WITHOUT filesystem isolation."
        )
        node_bin = shutil.which("node")
        if not node_bin:
            raise FileNotFoundError("Node.js is not installed. Cannot start WhatsApp bridge.")

        proc = await asyncio.create_subprocess_exec(
            node_bin,
            "dist/index.js",
            cwd=str(bridge_dir),
            env=env,
            stdout=stdout,
            stderr=stderr,
        )

    return proc
