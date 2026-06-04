import json
import os
import pytest
from pathlib import Path
from amberclaw.security.vault import SecretVault, resolved_secrets_context, vault as global_vault
from amberclaw.config.loader import load_config


def test_vault_flow(tmp_path: Path) -> None:
    """Test that vault correctly generates keys, encrypts, and decrypts secrets."""
    vault = SecretVault(key_dir=tmp_path)

    # Key generation check
    key_file = tmp_path / ".vault_key"
    assert not key_file.exists()
    
    # Store a secret
    vault.store_secret("my_key", "secret_value_123")
    assert key_file.exists()
    assert (tmp_path / "vault.enc").exists()

    # Retrieve secret
    assert vault.get_secret("my_key") == "secret_value_123"
    assert vault.get_secret("nonexistent") is None

    # Resolve secret
    assert vault.resolve_secret("vault://my_key") == "secret_value_123"
    assert vault.resolve_secret("vault://nonexistent") is None
    assert vault.resolve_secret("plain_text") == "plain_text"
    assert vault.resolve_secret(None) is None


def test_resolved_secrets_context_env_cleanup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that resolved_secrets_context cleans up environment variables correctly."""
    # Point global vault to temp path for isolation
    monkeypatch.setattr(global_vault, "base_dir", tmp_path)
    monkeypatch.setattr(global_vault, "key_file", tmp_path / ".vault_key")
    monkeypatch.setattr(global_vault, "vault_file", tmp_path / "vault.enc")
    monkeypatch.setattr(global_vault, "_fernet", None)

    global_vault.store_secret("test_env_key", "env_secret_999")

    env_var = "TEST_API_KEY_VAR"
    assert env_var not in os.environ

    # Happy path
    with resolved_secrets_context("vault://test_env_key", [env_var]) as key:
        assert key == "env_secret_999"
        assert os.environ[env_var] == "env_secret_999"

    assert env_var not in os.environ

    # Exception path
    try:
        with resolved_secrets_context("vault://test_env_key", [env_var]) as key:
            assert os.environ[env_var] == "env_secret_999"
            raise ValueError("Interruption")
    except ValueError:
        pass

    assert env_var not in os.environ


def test_config_secrets_migration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that loading a config with plain text keys migrates them to the vault."""
    config_file = tmp_path / "config.json"
    
    # Point global vault to temp path for isolation
    monkeypatch.setattr(global_vault, "base_dir", tmp_path)
    monkeypatch.setattr(global_vault, "key_file", tmp_path / ".vault_key")
    monkeypatch.setattr(global_vault, "vault_file", tmp_path / "vault.enc")
    monkeypatch.setattr(global_vault, "_fernet", None)

    raw_config = {
        "providers": {
            "openai": {
                "api_key": "sk-proj-super-secret",
                "api_base": "https://api.openai.com/v1"
            },
            "anthropic": {
                "api_key": "vault://providers/anthropic/api_key",
                "api_base": "https://api.anthropic.com/v1"
            }
        }
    }
    
    config_file.write_text(json.dumps(raw_config))

    # Load configuration; this should trigger auto-migration for openai
    config = load_config(config_file)

    # Verify the model has references
    assert config.providers.openai.api_key == "vault://providers/openai/api_key"
    assert config.providers.anthropic.api_key == "vault://providers/anthropic/api_key"

    # Verify the secret is stored in the vault
    assert global_vault.get_secret("providers/openai/api_key") == "sk-proj-super-secret"

    # Verify the file on disk was rewritten with the vault URI
    disk_data = json.loads(config_file.read_text())
    assert disk_data["providers"]["openai"]["apiKey"] == "vault://providers/openai/api_key"
