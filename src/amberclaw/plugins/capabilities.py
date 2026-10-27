# ruff: noqa: PLR0911, PLR0912, PLR0915, S108, PTH110
"""Capability-based sandboxing and process isolation for AmberClaw plugins."""

import contextlib
import ctypes
import os
import sys
from enum import StrEnum
from pathlib import Path

from loguru import logger

from amberclaw.security.egress_controller import (
    _egress_active,
    _egress_policy,
    apply_egress_patches,
)
from amberclaw.security.landlock import (
    ACCESS_FS_ALL,
    ACCESS_FS_READ,
    IS_LINUX,
    PR_SET_NO_NEW_PRIVS,
    SYS_LANDLOCK_CREATE_RULESET,
    SYS_LANDLOCK_RESTRICT_SELF,
    LandlockRulesetAttr,
    _add_path_rule,
)
from amberclaw.security.network_policy import NetworkPolicy


class PluginCapability(StrEnum):
    """Supported sandbox capabilities for third-party plugins."""

    FILESYSTEM_READ = "filesystem_read"
    FILESYSTEM_WRITE = "filesystem_write"
    NETWORK_ACCESS = "network_access"
    ENV_READ = "env_read"


def apply_sandbox_with_capabilities(
    capabilities: list[PluginCapability],
    workspace_path: Path | str,
    plugin_dir: Path | str,
) -> bool:
    """Restricts resources and capabilities of the current process.

    Enforces network access, env variable access, and Landlock filesystem path restrictions.
    """
    has_fs_read = PluginCapability.FILESYSTEM_READ in capabilities
    has_fs_write = PluginCapability.FILESYSTEM_WRITE in capabilities
    has_net = PluginCapability.NETWORK_ACCESS in capabilities
    has_env = PluginCapability.ENV_READ in capabilities

    # 1. Restrict Environment Variables
    if not has_env:
        essential = {"PATH", "LANG", "LC_ALL", "TERM", "PYTHONPATH"}
        for k in list(os.environ.keys()):
            if k not in essential and not k.startswith("AMBERCLAW_"):
                del os.environ[k]

    # 2. Restrict Network Access
    if not has_net:
        apply_egress_patches()
        _egress_active.set(True)
        _egress_policy.set(NetworkPolicy(allowed_hosts=[], allowed_ports=[]))

    # 3. Restrict Filesystem Access (Linux Landlock)
    if not IS_LINUX:
        logger.debug("Landlock sandboxing skipped: not on Linux.")
        return False

    try:
        libc = ctypes.CDLL(None)
    except Exception as e:
        logger.warning("Failed to load libc for Landlock: {}", e)
        return False

    attr = LandlockRulesetAttr()
    attr.handled_access_fs = ACCESS_FS_ALL

    ruleset_fd = libc.syscall(
        SYS_LANDLOCK_CREATE_RULESET,
        ctypes.byref(attr),
        ctypes.sizeof(attr),
        0,
    )
    if ruleset_fd < 0:
        logger.warning("Landlock ruleset creation failed.")
        return False

    try:
        # Crucial Python paths to keep interpreter functional
        paths_read_only = [
            "/usr",
            "/lib",
            "/lib64",
            "/etc",
            "/dev/null",
            "/dev/urandom",
            "/dev/zero",
        ]
        paths_read_only.append(sys.prefix)
        if hasattr(sys, "base_prefix"):
            paths_read_only.append(sys.base_prefix)
        if hasattr(sys, "exec_prefix"):
            paths_read_only.append(sys.exec_prefix)

        # Allow reading all sys.path modules and virtualenv packages
        for sp in sys.path:
            if sp and os.path.exists(sp):
                paths_read_only.append(str(Path(sp).resolve()))

        # Allow reading the plugin directory itself so it can import packages
        plugin_dir_str = str(Path(plugin_dir).resolve())
        paths_read_only.append(plugin_dir_str)

        # Add workspace path configuration
        workspace_str = str(Path(workspace_path).resolve())

        paths_read_write = []
        if has_fs_write:
            paths_read_write.append(workspace_str)
            paths_read_write.append("/tmp")
        elif has_fs_read:
            paths_read_only.append(workspace_str)
            paths_read_only.append("/tmp")

        # Add rules to Landlock
        for p in paths_read_write:
            if os.path.exists(p):
                _add_path_rule(libc, ruleset_fd, p, ACCESS_FS_ALL)

        for p in paths_read_only:
            if os.path.exists(p):
                _add_path_rule(libc, ruleset_fd, p, ACCESS_FS_READ)

        # Apply sandboxing context restrictions
        if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) < 0:
            os.close(ruleset_fd)
            return False

        if libc.syscall(SYS_LANDLOCK_RESTRICT_SELF, ruleset_fd, 0) < 0:
            os.close(ruleset_fd)
            return False

        os.close(ruleset_fd)
        logger.debug("Landlock sandboxing rules successfully applied.")
        return True
    except Exception as e:
        logger.exception("Error applying Landlock restrictions: {}", e)
        with contextlib.suppress(Exception):
            os.close(ruleset_fd)
        return False
