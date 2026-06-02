"""Pure Python implementation of Landlock LSM sandboxing on Linux systems."""

import ctypes
import os
import platform
import sys
from pathlib import Path

# Only define structures and symbols if on Linux
IS_LINUX = platform.system() == "Linux"

# Landlock structures
if IS_LINUX:
    class LandlockRulesetAttr(ctypes.Structure):
        _fields_ = [("handled_access_fs", ctypes.c_uint64)]

    class LandlockPathBeneathAttr(ctypes.Structure):
        _fields_ = [
            ("allowed_access", ctypes.c_uint64),
            ("parent_fd", ctypes.c_int32),
        ]
else:
    class LandlockRulesetAttr:
        pass

    class LandlockPathBeneathAttr:
        pass


# Access rights
LANDLOCK_ACCESS_FS_EXECUTE = 1 << 0
LANDLOCK_ACCESS_FS_WRITE_FILE = 1 << 1
LANDLOCK_ACCESS_FS_READ_FILE = 1 << 2
LANDLOCK_ACCESS_FS_READ_DIR = 1 << 3
LANDLOCK_ACCESS_FS_REMOVE_DIR = 1 << 4
LANDLOCK_ACCESS_FS_REMOVE_FILE = 1 << 5
LANDLOCK_ACCESS_FS_MAKE_CHAR = 1 << 6
LANDLOCK_ACCESS_FS_MAKE_DIR = 1 << 7
LANDLOCK_ACCESS_FS_MAKE_REG = 1 << 8
LANDLOCK_ACCESS_FS_MAKE_SOCK = 1 << 9
LANDLOCK_ACCESS_FS_MAKE_FIFO = 1 << 10
LANDLOCK_ACCESS_FS_MAKE_BLOCK = 1 << 11
LANDLOCK_ACCESS_FS_MAKE_SYM = 1 << 12
LANDLOCK_ACCESS_FS_REFER = 1 << 13
LANDLOCK_ACCESS_FS_TRUNCATE = 1 << 14

ACCESS_FS_READ = (
    LANDLOCK_ACCESS_FS_READ_FILE
    | LANDLOCK_ACCESS_FS_READ_DIR
    | LANDLOCK_ACCESS_FS_EXECUTE
)

ACCESS_FS_WRITE = (
    LANDLOCK_ACCESS_FS_WRITE_FILE
    | LANDLOCK_ACCESS_FS_REMOVE_DIR
    | LANDLOCK_ACCESS_FS_REMOVE_FILE
    | LANDLOCK_ACCESS_FS_MAKE_DIR
    | LANDLOCK_ACCESS_FS_MAKE_REG
    | LANDLOCK_ACCESS_FS_MAKE_SYM
    | LANDLOCK_ACCESS_FS_TRUNCATE
)

# Combine read and write
ACCESS_FS_ALL = ACCESS_FS_READ | ACCESS_FS_WRITE

# Syscalls (x86_64 and arm64 are identical)
SYS_LANDLOCK_CREATE_RULESET = 444
SYS_LANDLOCK_ADD_RULE = 445
SYS_LANDLOCK_RESTRICT_SELF = 446

PR_SET_NO_NEW_PRIVS = 38
LANDLOCK_RULE_PATH_BENEATH = 1


def _add_path_rule(libc: ctypes.CDLL, ruleset_fd: int, path: str, access: int) -> None:
    """Helper to add path restrictions to Landlock ruleset."""
    try:
        # Use O_PATH if available on Linux to avoid unnecessary resource read operations
        flags = getattr(os, "O_PATH", os.O_RDONLY)
        fd = os.open(path, flags | os.O_CLOEXEC)
    except Exception:
        return

    try:
        path_attr = LandlockPathBeneathAttr()
        path_attr.allowed_access = access
        path_attr.parent_fd = fd

        libc.syscall(
            SYS_LANDLOCK_ADD_RULE,
            ruleset_fd,
            LANDLOCK_RULE_PATH_BENEATH,
            ctypes.byref(path_attr),
            0,
        )
    except Exception:
        pass
    finally:
        os.close(fd)


def apply_sandbox(workspace_path: str | Path) -> bool:
    """Restricts filesystem operations for the current process.

    Allows read/write inside workspace_path and /tmp.
    Allows read-only access to standard system python, lib, and /etc configurations.
    """
    if not IS_LINUX:
        return False

    try:
        libc = ctypes.CDLL(None)
    except Exception:
        return False

    # Define ruleset
    attr = LandlockRulesetAttr()
    attr.handled_access_fs = ACCESS_FS_ALL

    ruleset_fd = libc.syscall(
        SYS_LANDLOCK_CREATE_RULESET,
        ctypes.byref(attr),
        ctypes.sizeof(attr),
        0,
    )
    if ruleset_fd < 0:
        # Landlock not supported or blocked by system
        return False

    try:
        # Set workspace path as read/write
        paths_read_write = [str(workspace_path), "/tmp", "/dev/null", "/dev/urandom", "/dev/zero"]
        paths_read_only = ["/usr", "/lib", "/lib64", "/etc"]

        # Add virtual environment paths to allowed reads
        paths_read_only.append(sys.prefix)
        if hasattr(sys, "base_prefix"):
            paths_read_only.append(sys.base_prefix)

        for p in paths_read_write:
            if os.path.exists(p):
                _add_path_rule(libc, ruleset_fd, p, ACCESS_FS_ALL)

        for p in paths_read_only:
            if os.path.exists(p):
                _add_path_rule(libc, ruleset_fd, p, ACCESS_FS_READ)

        # Enforce restrict self
        if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) < 0:
            os.close(ruleset_fd)
            return False

        if libc.syscall(SYS_LANDLOCK_RESTRICT_SELF, ruleset_fd, 0) < 0:
            os.close(ruleset_fd)
            return False

        os.close(ruleset_fd)
        return True
    except Exception:
        try:
            os.close(ruleset_fd)
        except Exception:
            pass
        return False
