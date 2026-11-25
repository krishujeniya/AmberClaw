"""Loads and parses blueprint specifications from YAML/JSON files and preset profiles."""

from pathlib import Path
from typing import Any

import yaml

from amberclaw.blueprints.schema import BlueprintSchema


class BlueprintLoader:
    """Loads BlueprintSchema instances from files, dictionaries, or built-in presets."""

    def __init__(self, presets_dir: Path | str | None = None) -> None:
        if presets_dir:
            self.presets_dir = Path(presets_dir)
        else:
            self.presets_dir = Path(__file__).parent / "presets"

    def load_from_dict(self, data: dict[str, Any]) -> BlueprintSchema:
        """Instantiate BlueprintSchema from a Python dictionary."""
        return BlueprintSchema(**data)

    def load_from_yaml_string(self, yaml_content: str) -> BlueprintSchema:
        """Parse YAML string and instantiate BlueprintSchema."""
        parsed = yaml.safe_load(yaml_content) or {}
        return self.load_from_dict(parsed)

    def load_from_file(self, file_path: Path | str) -> BlueprintSchema:
        """Load BlueprintSchema from a YAML or JSON file on disk."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Blueprint file not found: {path}")
        content = path.read_text(encoding="utf-8")
        return self.load_from_yaml_string(content)

    def load_preset(self, preset_name: str) -> BlueprintSchema:
        """Load a built-in preset blueprint (e.g. 'default', 'developer', 'minimal', 'paranoid')."""
        normalized_name = preset_name.lower().replace(".yaml", "").replace(".yml", "")
        preset_file = self.presets_dir / f"{normalized_name}.yaml"
        if not preset_file.is_file():
            raise FileNotFoundError(
                f"Preset blueprint '{preset_name}' not found at {preset_file}."
            )
        return self.load_from_file(preset_file)

    def list_available_presets(self) -> list[str]:
        """List all available preset blueprint names."""
        if not self.presets_dir.is_dir():
            return []
        return [p.stem for p in self.presets_dir.glob("*.yaml")]
