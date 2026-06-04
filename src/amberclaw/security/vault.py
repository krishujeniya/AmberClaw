"""Encrypted credential vault for AmberClaw.

Stores secrets encrypted at rest and resolves vault reference URIs.
"""

import json
import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from cryptography.fernet import Fernet
from loguru import logger


class SecretVault:
    """Manages secure key generation, encryption, storage, and retrieval."""

    def __init__(self, key_dir: Path | None = None) -> None:
        self.base_dir = key_dir or Path.home() / ".amberclaw"
        self.key_file = self.base_dir / ".vault_key"
        self.vault_file = self.base_dir / "vault.enc"
        self._fernet: Fernet | None = None

    def _get_fernet(self) -> Fernet:
        """Initialize and return the Fernet cipher suite."""
        if self._fernet is not None:
            return self._fernet

        # 1. Check environment variable
        key_str = os.environ.get("AMBERCLAW_VAULT_KEY")
        if key_str:
            try:
                key_bytes = key_str.encode("utf-8")
                self._fernet = Fernet(key_bytes)
                return self._fernet
            except Exception as e:
                logger.error("Invalid AMBERCLAW_VAULT_KEY env var: {}", e)

        # 2. Check file
        self.base_dir.mkdir(parents=True, exist_ok=True)
        if self.key_file.exists():
            try:
                key_bytes = self.key_file.read_bytes()
                self._fernet = Fernet(key_bytes)
                return self._fernet
            except Exception as e:
                logger.error("Failed to read vault key file: {}", e)

        # 3. Generate key
        try:
            key_bytes = Fernet.generate_key()
            self.key_file.write_bytes(key_bytes)
            self.key_file.chmod(0o600)
            self._fernet = Fernet(key_bytes)
            return self._fernet
        except Exception as e:
            logger.error("Failed to generate and save vault key: {}", e)
            fallback_key = Fernet.generate_key()
            self._fernet = Fernet(fallback_key)
            return self._fernet

    def _load_vault_data(self) -> dict[str, str]:
        """Load and decrypt the vault database."""
        if not self.vault_file.exists():
            return {}

        try:
            encrypted_data = self.vault_file.read_bytes()
            if not encrypted_data:
                return {}
            fernet = self._get_fernet()
            decrypted_data = fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode("utf-8"))
        except Exception as e:
            logger.error("Failed to load/decrypt vault: {}", e)
            return {}

    def _save_vault_data(self, data: dict[str, str]) -> None:
        """Encrypt and save the vault database."""
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            serialized = json.dumps(data).encode("utf-8")
            fernet = self._get_fernet()
            encrypted_data = fernet.encrypt(serialized)
            self.vault_file.write_bytes(encrypted_data)
            self.vault_file.chmod(0o600)
        except Exception as e:
            logger.error("Failed to save/encrypt vault: {}", e)

    def store_secret(self, name: str, value: str) -> None:
        """Encrypt and store a secret in the vault."""
        data = self._load_vault_data()
        data[name] = value
        self._save_vault_data(data)

    def get_secret(self, name: str) -> str | None:
        """Retrieve and decrypt a secret from the vault."""
        data = self._load_vault_data()
        return data.get(name)

    def resolve_secret(self, value: str | None) -> str | None:
        """Resolve a vault reference URL or return the string as-is."""
        if not value:
            return value
        if value.startswith("vault://"):
            secret_name = value[len("vault://") :]
            secret = self.get_secret(secret_name)
            if secret is not None:
                return secret
            logger.warning("Secret '{}' not found in vault.", secret_name)
            return None
        return value


# Global singleton instance
vault = SecretVault()


@contextmanager
def resolved_secrets_context(
    api_key: str | None, env_vars: list[str] | None = None
) -> Generator[str | None, None, None]:
    """Temporarily resolve a vault key and inject it into os.environ."""
    resolved_key = vault.resolve_secret(api_key)
    added_env_keys: list[str] = []

    if resolved_key and env_vars:
        for env_key in env_vars:
            if env_key not in os.environ:
                os.environ[env_key] = resolved_key
                added_env_keys.append(env_key)

    try:
        yield resolved_key
    finally:
        for env_key in added_env_keys:
            os.environ.pop(env_key, None)
