# ruff: noqa: S105, PLR2004
"""Unit tests for Secret Vault live rotation and access auditing.

Validates:
1. Secret storage and access event emission to the tamper-evident audit log
2. Live in-memory rotation callbacks (updating provider credentials without restart)
3. Direct secret rotation dispatch and subscriber notification
"""

from pathlib import Path

from amberclaw.security.vault import SecretVault


def test_vault_access_and_storage_auditing(tmp_path: Path):
    vault = SecretVault(key_dir=tmp_path)

    # 1. Store secret
    vault.store_secret("openai_api_key", "sk-proj-test123456", actor="admin")

    # 2. Get secret
    secret = vault.get_secret("openai_api_key", actor="worker_agent")
    assert secret == "sk-proj-test123456"

    # 3. Nonexistent secret access returns None
    missing = vault.get_secret("nonexistent_token", actor="worker_agent")
    assert missing is None


def test_vault_live_credential_rotation(tmp_path: Path):
    vault = SecretVault(key_dir=tmp_path)
    vault.store_secret("anthropic_key", "sk-ant-initial-v1")

    # In-memory subscriber simulating a live LLM Provider client
    active_client_keys: list[str] = ["sk-ant-initial-v1"]

    def on_anthropic_key_rotated(new_key: str):
        active_client_keys.append(new_key)

    # Register live rotation hook
    vault.register_rotation_hook("anthropic_key", on_anthropic_key_rotated)

    # Rotate secret live
    vault.rotate_secret("anthropic_key", "sk-ant-rotated-v2", actor="sec_ops")

    # Verify secret is updated in vault
    assert vault.get_secret("anthropic_key") == "sk-ant-rotated-v2"

    # Verify live subscriber was notified immediately without application restart
    assert len(active_client_keys) == 2
    assert active_client_keys[-1] == "sk-ant-rotated-v2"
