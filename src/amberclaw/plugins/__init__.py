"""AmberClaw plugins module."""

from amberclaw.config.schema import PluginsModuleConfig
from amberclaw.plugins.capabilities import PluginCapability
from amberclaw.plugins.manager import PluginManager, PluginProxyTool
from amberclaw.plugins.registry import PluginManifest, PluginRegistry

__all__ = [
    "PluginCapability",
    "PluginManager",
    "PluginManifest",
    "PluginProxyTool",
    "PluginRegistry",
    "PluginsModuleConfig",
]
