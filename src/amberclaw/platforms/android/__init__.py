"""AmberClaw Android Termux platform integration package."""

import os
from pathlib import Path

from pydantic import BaseModel, Field


class AndroidPlatformConfig(BaseModel):
    """Configuration specific to Android Termux deployments."""

    is_termux: bool = Field(
        default_factory=lambda: Path("/data/data/com.termux").exists()
    )
    termux_prefix: str = Field(
        default=os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
    )
    enable_termux_api: bool = Field(default=True)


def is_android_environment() -> bool:
    """Return True if running inside an Android Termux userland."""
    return (
        Path("/data/data/com.termux").exists()
        or os.environ.get("AMBERCLAW_PLATFORM") == "android"
    )


def get_android_scripts_dir() -> Path:
    """Return path to packaged Android bootstrap scripts."""
    return Path(__file__).parent / "scripts"


__all__ = [
    "AndroidPlatformConfig",
    "get_android_scripts_dir",
    "is_android_environment",
]
