"""
AmberClaw amberclaw.terminal module.
"""

from pydantic import BaseModel, Field

from amberclaw.terminal.base import BaseTerminalBackend
from amberclaw.terminal.daytona import DaytonaTerminalBackend
from amberclaw.terminal.docker import DockerTerminalBackend
from amberclaw.terminal.factory import BackendFactory
from amberclaw.terminal.local import LocalTerminalBackend
from amberclaw.terminal.modal import ModalTerminalBackend
from amberclaw.terminal.singularity import SingularityTerminalBackend
from amberclaw.terminal.ssh import SSHTerminalBackend
from amberclaw.terminal.vercel import VercelTerminalBackend


class TerminalModuleConfig(BaseModel):
    """Configuration for the amberclaw.terminal module."""
    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = [
    "BackendFactory",
    "BaseTerminalBackend",
    "DaytonaTerminalBackend",
    "DockerTerminalBackend",
    "LocalTerminalBackend",
    "ModalTerminalBackend",
    "SSHTerminalBackend",
    "SingularityTerminalBackend",
    "TerminalModuleConfig",
    "VercelTerminalBackend",
]
