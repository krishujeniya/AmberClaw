"""Unit tests for AmberClaw state persistence, checkpoints, and schema migrations."""

from pathlib import Path

import pytest

from amberclaw.state.manager import StateManager
from amberclaw.state.migration import StateMigrator


def test_state_manager_in_memory_and_checkpoints():
    mgr = StateManager()

    # Save and retrieve
    initial_turns = 3
    mutated_turns = 10
    expected_keys_count = 2

    mgr.save_state("session:1", {"user_id": "u123", "turns": initial_turns})
    mgr.save_state("session:2", {"user_id": "u456", "turns": 1})

    assert mgr.get_state("session:1") == {"user_id": "u123", "turns": initial_turns}
    assert len(mgr.list_keys()) == expected_keys_count

    # Create checkpoint
    meta = mgr.create_checkpoint("cp-initial", description="Before mutation")
    assert meta.checkpoint_id == "cp-initial"
    assert set(meta.state_keys) == {"session:1", "session:2"}

    # Mutate state
    mgr.save_state("session:1", {"user_id": "u123", "turns": mutated_turns})
    mgr.delete_state("session:2")
    assert mgr.get_state("session:1")["turns"] == mutated_turns
    assert mgr.get_state("session:2") is None

    # Restore checkpoint
    assert mgr.restore_checkpoint("cp-initial") is True
    assert mgr.get_state("session:1")["turns"] == initial_turns
    assert mgr.get_state("session:2") is not None


def test_state_manager_disk_persistence(tmp_path: Path):
    storage_dir = tmp_path / "state_data"
    mgr1 = StateManager(storage_dir=storage_dir)

    mgr1.save_state("config:main", {"theme": "amber", "debug": True})
    mgr1.save_state("stats", {"active_agents": 4})

    # Instantiate second manager pointing to same disk storage
    mgr2 = StateManager(storage_dir=storage_dir)
    assert mgr2.get_state("config:main") == {"theme": "amber", "debug": True}
    assert mgr2.get_state("stats") == {"active_agents": 4}

    # Delete in mgr2 reflects in disk
    mgr2.delete_state("stats")
    mgr3 = StateManager(storage_dir=storage_dir)
    assert mgr3.get_state("stats") is None


def test_state_migrator():
    migrator = StateMigrator()

    # Step 1: v1 -> v2 (renames 'agent_name' to 'agent_id' and adds default role)
    def v1_to_v2(payload: dict) -> dict:
        p = payload.copy()
        p["agent_id"] = p.pop("agent_name", "unnamed")
        p["role"] = "assistant"
        return p

    # Step 2: v2 -> v3 (transforms 'tools' list to dict)
    def v2_to_v3(payload: dict) -> dict:
        p = payload.copy()
        tools_list = p.pop("tools", [])
        p["tools_config"] = {t: {"enabled": True} for t in tools_list}
        return p

    migrator.register_step(from_version=1, to_version=2, transform_fn=v1_to_v2, description="Migrate v1 to v2")
    migrator.register_step(from_version=2, to_version=3, transform_fn=v2_to_v3, description="Migrate v2 to v3")

    old_state = {
        "schema_version": 1,
        "agent_name": "agent_alpha",
        "tools": ["read_file", "write_file"],
    }

    # Migrate v1 -> v3
    target_version = 3
    new_state = migrator.migrate(old_state, target_version=target_version)
    assert new_state["schema_version"] == target_version
    assert new_state["agent_id"] == "agent_alpha"
    assert new_state["role"] == "assistant"
    assert "tools_config" in new_state
    assert new_state["tools_config"]["read_file"]["enabled"] is True

    # Error when no path exists
    with pytest.raises(ValueError):
        migrator.migrate({"schema_version": 1}, target_version=99)
