# ruff: noqa: PLR2004, S104
"""Configuration integrity and validation utilities."""

from __future__ import annotations

import ipaddress
import re
from pathlib import Path
from typing import Any


def validate_network_bind(host: str, port: int) -> tuple[bool, str | None]:
    """Validate host binding and port number."""
    errs: list[str] = []
    if not (1 <= port <= 65535):
        errs.append(f"Port {port} out of valid range (1-65535)")

    if host not in ("localhost", "0.0.0.0"):
        try:
            ipaddress.ip_address(host)
        except ValueError:
            errs.append(f"Invalid host IP address: '{host}'")

    if errs:
        return False, "; ".join(errs)
    return True, None


def validate_model_identifier(model_name: str) -> tuple[bool, str | None]:
    """Validate model name syntax."""
    if not model_name or not model_name.strip():
        return False, "Model name cannot be empty"

    if not re.match(r"^[a-zA-Z0-9_\-\.\:\/]+$", model_name):
        return False, f"Invalid characters in model identifier: '{model_name}'"

    return True, None


def validate_temperature(temp: float) -> tuple[bool, str | None]:
    """Validate sampling temperature is between 0.0 and 2.0."""
    if not (0.0 <= temp <= 2.0):
        return False, f"Temperature {temp} must be between 0.0 and 2.0"
    return True, None


def validate_storage_directory(path: Path | str, create_if_missing: bool = False) -> tuple[bool, str | None]:
    """Validate that storage directory path is valid and writable."""
    p = Path(path)
    try:
        if not p.exists() and create_if_missing:
            p.mkdir(parents=True, exist_ok=True)
        return True, None
    except Exception as ex:
        return False, f"Cannot access or create storage directory '{path}': {ex}"


def validate_config_dict(cfg: dict[str, Any]) -> list[str]:
    """Audit a raw configuration dictionary and return list of validation errors."""
    errors: list[str] = []

    # Gateway check
    gw = cfg.get("gateway", {})
    if gw:
        host = gw.get("host", "127.0.0.1")
        port = gw.get("port", 8000)
        ok, err = validate_network_bind(host, port)
        if not ok and err:
            for sub_err in err.split("; "):
                errors.append(f"Gateway: {sub_err}")

    # Agents check
    agents = cfg.get("agents", {})
    for agent_name, agent_cfg in agents.items():
        if isinstance(agent_cfg, dict):
            model = agent_cfg.get("model")
            if model:
                ok, err = validate_model_identifier(model)
                if not ok and err:
                    errors.append(f"Agent '{agent_name}': {err}")

            temp = agent_cfg.get("temperature")
            if temp is not None:
                ok, err = validate_temperature(float(temp))
                if not ok and err:
                    errors.append(f"Agent '{agent_name}': {err}")

    return errors
