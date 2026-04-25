"""Configuration loading utilities."""

import json
from pathlib import Path
from typing import Any

from amberclaw.config.schema import Config


# Global variable to store current config path (for multi-instance support)
_current_config_path: Path | None = None


def set_config_path(path: Path) -> None:
    """Set the current config path (used to derive data directory)."""
    global _current_config_path
    _current_config_path = path


def get_config_path() -> Path:
    """Get the configuration file path. Checks .yaml then .json."""
    if _current_config_path:
        return _current_config_path

    base = Path.home() / ".amberclaw"
    yaml_path = base / "config.yaml"
    if yaml_path.exists():
        return yaml_path
    yml_path = base / "config.yml"
    if yml_path.exists():
        return yml_path
    return base / "config.json"


def load_config(config_path: Path | None = None) -> Config:
    """
    Load configuration from file or create default.
    Supports both JSON and YAML formats.
    """
    path = config_path or get_config_path()

    if path.exists():
        try:
            content = path.read_text(encoding="utf-8")
            if path.suffix in (".yaml", ".yml"):
                import yaml

                data = yaml.safe_load(content)
            else:
                data = json.loads(content)

            if data:
                data = _migrate_config(data)
                return Config.model_validate(data)
        except Exception as e:
            print(f"Warning: Failed to load config from {path}: {e}")
            print("Using default configuration.")

    return Config()


def save_config(config: Config, config_path: Path | None = None) -> None:
    """
    Save configuration to file.

    Args:
        config: Configuration to save.
        config_path: Optional path to save to. Uses default if not provided.
    """
    path = config_path or get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    data = config.model_dump(by_alias=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _migrate_config(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate old config formats to current."""
    # Move tools.exec.restrictToWorkspace → tools.restrictToWorkspace
    tools = data.get("tools", {})
    if not isinstance(tools, dict):
        tools = {}
    exec_cfg = tools.get("exec", {})
    if (
        isinstance(exec_cfg, dict)
        and "restrictToWorkspace" in exec_cfg
        and "restrictToWorkspace" not in tools
    ):
        tools["restrictToWorkspace"] = exec_cfg.pop("restrictToWorkspace")
    return data


def load_runtime_config(config: str | None = None, workspace: str | None = None) -> Config:
    """Load config and optionally override the active workspace."""
    config_path = None
    if config:
        config_path = Path(config).expanduser().resolve()
        if not config_path.exists():
            # Note: We don't use Typer output here to keep config package clean
            # The caller (CLI) will handle the specific error reporting if needed
            raise FileNotFoundError(f"Config file not found: {config_path}")
        set_config_path(config_path)

    loaded = load_config(config_path)
    if workspace:
        loaded.agents.defaults.workspace = workspace
    return loaded
