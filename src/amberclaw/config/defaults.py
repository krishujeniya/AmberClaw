"""Default configuration values and templates for AmberClaw."""

from __future__ import annotations

from typing import Any

DEFAULT_GATEWAY_HOST = "127.0.0.1"
DEFAULT_GATEWAY_PORT = 8000
DEFAULT_WEB_PORT = 8080

DEFAULT_MODEL = "gpt-4o"
DEFAULT_FAST_MODEL = "gpt-4o-mini"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.7

DEFAULT_SANDBOX_TYPE = "docker"
DEFAULT_AUDIT_LOG_DIR = "logs"
DEFAULT_MEMORY_DIR = "memory"
DEFAULT_STORAGE_DIR = "data"


def get_default_config_dict() -> dict[str, Any]:
    """Return default configuration dictionary for a fresh AmberClaw installation."""
    return {
        "agents": {
            "default": {
                "model": DEFAULT_MODEL,
                "temperature": DEFAULT_TEMPERATURE,
                "max_tokens": DEFAULT_MAX_TOKENS,
            }
        },
        "gateway": {
            "host": DEFAULT_GATEWAY_HOST,
            "port": DEFAULT_GATEWAY_PORT,
        },
        "security": {
            "sandbox": DEFAULT_SANDBOX_TYPE,
            "audit_enabled": True,
            "log_dir": DEFAULT_AUDIT_LOG_DIR,
        },
        "channels": {},
        "providers": {},
    }
