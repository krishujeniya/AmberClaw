"""Subagent isolation policies and sandbox containment boundary enforcement."""

import os
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, Field


class IsolationPolicy(BaseModel):
    """Configuration governing subagent execution containment and resource limits."""

    workspace_root: Path = Field(
        ..., description="Root directory subagent is allowed to access"
    )
    allowed_paths: list[Path] = Field(
        default_factory=list,
        description="Additional absolute paths the subagent may read or access",
    )
    read_only: bool = Field(
        default=False, description="Whether subagent is prohibited from disk writes"
    )
    allow_network: bool = Field(
        default=True, description="Whether outbound network requests are permitted"
    )
    max_memory_mb: int = Field(
        default=512, ge=64, description="Maximum resident memory allowed in MB"
    )
    max_execution_time: float = Field(
        default=300.0, ge=1.0, description="Max execution duration in seconds"
    )
    env_allowlist: list[str] = Field(
        default_factory=lambda: [
            "PATH",
            "HOME",
            "LANG",
            "LC_ALL",
            "TERM",
            "USER",
            "SHELL",
            "TMPDIR",
        ],
        description="Whitelisted environment variables safe for worker child processes",
    )


class SubagentIsolationContext:
    """Enforces sandbox boundaries and validates system interactions for subagents."""

    def __init__(self, policy: IsolationPolicy) -> None:
        self.policy = policy
        self._resolved_workspace = policy.workspace_root.resolve()
        self._resolved_allowed = [p.resolve() for p in policy.allowed_paths]

    def is_path_allowed(self, target_path: Path | str, write: bool = False) -> bool:
        """Verify whether a filesystem path is permitted under the isolation policy."""
        if write and self.policy.read_only:
            logger.warning(
                "Write attempted to '{}' under read-only isolation policy", target_path
            )
            return False

        try:
            resolved = Path(target_path).resolve()
        except Exception:
            return False

        # Check if path is contained in workspace_root
        if (
            resolved == self._resolved_workspace
            or self._resolved_workspace in resolved.parents
        ):
            return True

        # Check additional allowed paths
        for allowed in self._resolved_allowed:
            if resolved == allowed or allowed in resolved.parents:
                return True

        logger.warning(
            "Access denied to '{}': path is outside allowed sandbox root '{}'",
            target_path,
            self._resolved_workspace,
        )
        return False

    def validate_path(self, target_path: Path | str, write: bool = False) -> Path:
        """Validate path containment, returning resolved Path or raising PermissionError."""
        if not self.is_path_allowed(target_path, write=write):
            raise PermissionError(
                f"Path '{target_path}' violates subagent isolation policy (outside workspace or write forbidden)"
            )
        return Path(target_path).resolve()

    def sanitize_environment(
        self,
        base_env: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Produce a clean, isolated environment dictionary containing only allowlisted keys."""
        source = base_env if base_env is not None else dict(os.environ)
        cleaned: dict[str, str] = {}

        for key in self.policy.env_allowlist:
            if key in source:
                cleaned[key] = source[key]

        return cleaned

    def check_memory(self, memory_usage_mb: float) -> bool:
        """Verify if current memory usage stays within the configured policy ceiling."""
        if memory_usage_mb > self.policy.max_memory_mb:
            logger.warning(
                "Subagent memory usage {:.1f}MB exceeds limit {}MB",
                memory_usage_mb,
                self.policy.max_memory_mb,
            )
            return False
        return True
