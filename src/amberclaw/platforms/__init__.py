"""AmberClaw cross-platform abstraction layer and host optimization."""

from enum import StrEnum

from pydantic import BaseModel, Field

from amberclaw.platforms.manager import PlatformManager


class PlatformType(StrEnum):
    """Supported host operating system platforms."""

    LINUX = "linux"
    ANDROID_TERMUX = "android_termux"
    WINDOWS = "windows"
    MACOS = "macos"
    UNKNOWN = "unknown"


class PlatformsModuleConfig(BaseModel):
    """Configuration for the amberclaw.platforms module."""

    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = [
    "PlatformManager",
    "PlatformType",
    "PlatformsModuleConfig",
]
