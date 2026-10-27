# ruff: noqa: PLR2004, S104
"""Unit tests for AmberClaw config defaults and validation utilities."""

from pathlib import Path

from amberclaw.config.defaults import (
    DEFAULT_GATEWAY_HOST,
    DEFAULT_GATEWAY_PORT,
    DEFAULT_MODEL,
    get_default_config_dict,
)
from amberclaw.config.validators import (
    validate_config_dict,
    validate_model_identifier,
    validate_network_bind,
    validate_storage_directory,
    validate_temperature,
)


def test_default_config_dictionary():
    cfg = get_default_config_dict()
    assert cfg["gateway"]["host"] == DEFAULT_GATEWAY_HOST
    assert cfg["gateway"]["port"] == DEFAULT_GATEWAY_PORT
    assert cfg["agents"]["default"]["model"] == DEFAULT_MODEL
    assert cfg["security"]["audit_enabled"] is True


def test_validate_network_bind():
    # Valid binds
    ok, err = validate_network_bind("127.0.0.1", 8000)
    assert ok is True and err is None

    ok, err = validate_network_bind("0.0.0.0", 443)
    assert ok is True and err is None

    # Invalid port
    ok, err = validate_network_bind("127.0.0.1", 70000)
    assert ok is False and "out of valid range" in err

    # Invalid host IP
    ok, err = validate_network_bind("999.999.999.999", 8080)
    assert ok is False and "Invalid host" in err


def test_validate_model_identifier():
    ok, err = validate_model_identifier("gpt-4o")
    assert ok is True and err is None

    ok, err = validate_model_identifier("ollama/llama3.3:latest")
    assert ok is True and err is None

    # Empty
    ok, err = validate_model_identifier("")
    assert ok is False and "cannot be empty" in err

    # Illegal chars
    ok, err = validate_model_identifier("gpt-4o; rm -rf /")
    assert ok is False and "Invalid characters" in err


def test_validate_temperature():
    ok, err = validate_temperature(0.7)
    assert ok is True and err is None

    ok, err = validate_temperature(2.5)
    assert ok is False and "must be between" in err


def test_validate_storage_directory(tmp_path: Path):
    target = tmp_path / "sub" / "dir"
    ok, err = validate_storage_directory(target, create_if_missing=True)
    assert ok is True and err is None
    assert target.exists()


def test_validate_config_dict():
    # Valid dict
    valid = {
        "gateway": {"host": "127.0.0.1", "port": 8000},
        "agents": {
            "default": {"model": "claude-3-5-sonnet-20241022", "temperature": 0.5}
        },
    }
    assert validate_config_dict(valid) == []

    # Invalid dict with multiple issues
    invalid = {
        "gateway": {"host": "bad_host", "port": 99999},
        "agents": {
            "worker": {"model": "bad model!@", "temperature": 5.0}
        },
    }
    errors = validate_config_dict(invalid)
    assert len(errors) == 4
    assert any("out of valid range" in e for e in errors)
    assert any("Invalid host" in e for e in errors)
    assert any("Invalid characters" in e for e in errors)
    assert any("must be between" in e for e in errors)
