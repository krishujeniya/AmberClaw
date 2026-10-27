"""AmberClaw Platforms: Cross-platform bridge and manager."""

import os
import sys
from pathlib import Path

from loguru import logger


class PlatformManager:
    """Detects and optimizes AmberClaw for Android, Linux, or Windows."""

    @staticmethod
    def get_platform() -> str:
        """Identify host environment platform."""
        if Path("/data/data/com.termux").exists():
            return "android_termux"
        if sys.platform.startswith("linux"):
            return "linux"
        if sys.platform == "win32":
            return "windows"
        return "unknown"

    @staticmethod
    def apply_platform_optimizations() -> None:
        """Configure platform-specific execution parameters."""
        platform = PlatformManager.get_platform()
        logger.info("Detected environment platform: {}", platform)

        if platform == "android_termux":
            os.environ["AMBERCLAW_PLATFORM"] = "android"
            logger.info("Applying Android Termux environmental adjustments...")
        elif platform == "windows":
            logger.info("Optimizing terminal streams for Windows environments...")
