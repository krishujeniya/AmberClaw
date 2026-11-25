"""Unit tests for AmberClaw platform detection and Android Termux package."""

from pathlib import Path

from amberclaw.platforms.android import (
    AndroidPlatformConfig,
    get_android_scripts_dir,
    is_android_environment,
)
from amberclaw.platforms.manager import PlatformManager
from amberclaw.templates.memory import get_default_memory_template


def test_platform_manager_detection():
    plat = PlatformManager.get_platform()
    assert plat in ("linux", "windows", "android_termux", "unknown")

    # Optimization call executes without crashing
    PlatformManager.apply_platform_optimizations()


def test_android_environment_utilities(monkeypatch):
    assert isinstance(is_android_environment(), bool)
    scripts_dir = get_android_scripts_dir()
    assert isinstance(scripts_dir, Path)

    monkeypatch.setenv("AMBERCLAW_PLATFORM", "android")
    assert is_android_environment() is True

    cfg = AndroidPlatformConfig()
    assert isinstance(cfg.enable_termux_api, bool)


def test_memory_template_loading():
    content = get_default_memory_template()
    assert "Memory" in content
