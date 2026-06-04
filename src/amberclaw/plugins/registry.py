"""Plugin registry and manifest schema validation."""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field
from loguru import logger

from amberclaw.plugins.capabilities import PluginCapability


class PluginManifest(BaseModel):
    """Schema for plugin.yaml files defining metadata and requirements."""

    name: str = Field(..., description="Unique name identifier of the plugin")
    version: str = Field(..., description="Semantic version of the plugin")
    description: str = Field("", description="Human-readable description of the plugin's tools")
    entrypoint: str = Field(..., description="Entrypoint python script path relative to plugin dir (e.g. main.py)")
    capabilities: list[PluginCapability] = Field(
        default_factory=list, description="Explicit sandbox permissions requested by this plugin"
    )


class PluginRegistry:
    """Discovers and validates third-party plugin manifest configurations."""

    def __init__(self, plugins_dir: Path) -> None:
        self.plugins_dir = plugins_dir
        self.plugins: dict[str, tuple[Path, PluginManifest]] = {}

    def discover_plugins(self) -> dict[str, PluginManifest]:
        """Scans the plugins folder and loads all valid plugin manifests.

        Returns:
            A mapping from plugin name to verified PluginManifest schema.
        """
        self.plugins.clear()
        if not self.plugins_dir.exists():
            logger.debug("Plugin directory does not exist: {}", self.plugins_dir)
            return {}

        for item in self.plugins_dir.iterdir():
            if item.is_dir():
                manifest_path = item / "plugin.yaml"
                if manifest_path.exists():
                    try:
                        content = manifest_path.read_text(encoding="utf-8")
                        data = yaml.safe_load(content) or {}
                        manifest = PluginManifest.model_validate(data)
                        self.plugins[manifest.name] = (item, manifest)
                    except Exception as e:
                        logger.error(
                            "Failed to load or validate plugin manifest at {}: {}",
                            manifest_path,
                            e,
                        )

        return {name: manifest for name, (_, manifest) in self.plugins.items()}
