"""AmberClaw plugins module."""

from amberclaw.config.schema import PluginsModuleConfig
from amberclaw.plugins.capabilities import PluginCapability
from amberclaw.plugins.registry import PluginManifest, PluginRegistry
from amberclaw.plugins.manager import PluginManager, PluginProxyTool

__all__ = [
    "PluginsModuleConfig",
    "PluginCapability",
    "PluginManifest",
    "PluginRegistry",
    "PluginManager",
    "PluginProxyTool",
]
