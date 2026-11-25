"""AmberClaw plugins module.

Exports are resolved lazily so the out-of-process plugin host can import
:mod:`amberclaw.plugins.host` without pulling the full agent stack (the
manager imports agent tools) into every plugin subprocess.
"""

from importlib import import_module
from typing import Any

_LAZY_EXPORTS: dict[str, str] = {
    "PluginCapability": "amberclaw.plugins.capabilities",
    "PluginManager": "amberclaw.plugins.manager",
    "PluginProxyTool": "amberclaw.plugins.manager",
    "PluginManifest": "amberclaw.plugins.registry",
    "PluginRegistry": "amberclaw.plugins.registry",
    "PluginsModuleConfig": "amberclaw.config.schema",
}

__all__ = [
    "PluginCapability",
    "PluginManager",
    "PluginManifest",
    "PluginProxyTool",
    "PluginRegistry",
    "PluginsModuleConfig",
]


def __getattr__(name: str) -> Any:
    """Resolve a public plugin symbol on first access and cache it."""
    module_path = _LAZY_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    value = getattr(import_module(module_path), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
