"""Process and resource isolation mechanisms for AmberClaw execution sandboxes."""

import contextlib
import sys
from collections.abc import Callable

from pydantic import BaseModel, Field

# Only import resource on UNIX-like platforms
try:
    import resource
except ImportError:
    resource = None  # type: ignore[assignment]


class ResourceLimits(BaseModel):
    """Resource bounds applied to agent-spawned child processes."""

    max_memory_bytes: int = Field(default=512 * 1024 * 1024, ge=1024 * 1024, description="Virtual memory cap in bytes")
    max_cpu_seconds: int = Field(default=30, ge=1, description="Max CPU time in seconds")
    max_open_files: int = Field(default=256, ge=16, description="Max open file descriptors")
    max_processes: int = Field(default=64, ge=1, description="Max processes/threads")


class ProcessIsolationConfig(BaseModel):
    """Isolation configuration for sandboxed subprocesses."""

    enabled: bool = Field(default=True, description="Whether process isolation is enabled")
    limits: ResourceLimits = Field(default_factory=ResourceLimits)
    prevent_new_privileges: bool = Field(default=True, description="Enforce PR_SET_NO_NEW_PRIVS")


def apply_resource_limits(limits: ResourceLimits) -> None:
    """Set process resource limits on POSIX systems."""
    if resource is None or sys.platform == "win32":
        return

    with contextlib.suppress(ValueError, OSError):
        resource.setrlimit(resource.RLIMIT_AS, (limits.max_memory_bytes, limits.max_memory_bytes))

    with contextlib.suppress(ValueError, OSError):
        resource.setrlimit(resource.RLIMIT_CPU, (limits.max_cpu_seconds, limits.max_cpu_seconds))

    with contextlib.suppress(ValueError, OSError):
        resource.setrlimit(resource.RLIMIT_NOFILE, (limits.max_open_files, limits.max_open_files))

    with contextlib.suppress(ValueError, OSError):
        if hasattr(resource, "RLIMIT_NPROC"):
            resource.setrlimit(resource.RLIMIT_NPROC, (limits.max_processes, limits.max_processes))


def get_preexec_isolation_fn(config: ProcessIsolationConfig) -> Callable[[], None] | None:
    """Generate a preexec_fn for subprocess.Popen to enforce isolation."""
    if not config.enabled or sys.platform == "win32":
        return None

    def _preexec() -> None:
        apply_resource_limits(config.limits)

    return _preexec
