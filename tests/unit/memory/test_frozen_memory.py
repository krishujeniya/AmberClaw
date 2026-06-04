# ruff: noqa: E501
"""Unit tests for the Frozen-Snapshot Persistent Memory system."""

from amberclaw.memory.frozen_memory import FrozenSnapshotMemory


def test_frozen_memory_default_initialization(tmp_path):
    # Instantiate memory with a temporary workspace
    memory = FrozenSnapshotMemory(workspace=tmp_path)
    
    assert memory.user_path.exists()
    assert memory.memory_path.exists()
    
    # Read the auto-generated templates
    assert "User Profile" in memory.user_profile
    assert "Long-Term Memory" in memory.memory_facts


def test_frozen_memory_immutability_and_caching(tmp_path):
    memory = FrozenSnapshotMemory(workspace=tmp_path)
    
    # Pre-populate custom contents
    memory.user_path.write_text("# Custom Profile\n- Name: Test User", encoding="utf-8")
    memory.memory_path.write_text("# Custom Memory\n- Fact: Likes cats", encoding="utf-8")
    
    # Read once to populate cache
    profile_before = memory.user_profile
    facts_before = memory.memory_facts
    
    assert "Test User" in profile_before
    assert "Likes cats" in facts_before
    
    # Modify files on disk
    memory.user_path.write_text("# Changed Profile\n- Name: New Name", encoding="utf-8")
    memory.memory_path.write_text("# Changed Memory\n- Fact: Hates cats", encoding="utf-8")
    
    # Ensure cache is immutable and doesn't change
    assert memory.user_profile == profile_before
    assert memory.memory_facts == facts_before
    assert "New Name" not in memory.user_profile
    
    # Trigger explicit reload
    memory.reload()
    
    # Verify new data is loaded
    assert "New Name" in memory.user_profile
    assert "Hates cats" in memory.memory_facts


def test_frozen_memory_injection_block(tmp_path):
    memory = FrozenSnapshotMemory(workspace=tmp_path)
    memory.user_path.write_text("User Details Here", encoding="utf-8")
    memory.memory_path.write_text("Long Term Memory Here", encoding="utf-8")
    
    block = memory.get_injection_block()
    
    assert "User Details Here" in block
    assert "Long Term Memory Here" in block
    assert "Immutable snapshot loaded at session start" in block
