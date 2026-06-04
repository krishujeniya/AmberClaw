# ruff: noqa: PLR2004, E501
"""Unit tests for the Memory Manager Orchestrator."""

import pytest

from amberclaw.memory.manager import MemoryManager


@pytest.mark.asyncio
async def test_memory_manager_context_recall(tmp_path):
    # Initialize in context recall mode
    manager = MemoryManager(workspace=tmp_path, recall_mode="context", write_frequency="turn")
    
    # Add turns
    await manager.add_turn("session_abc", "user", "Hello first")
    await manager.add_turn("session_abc", "assistant", "Response first")
    await manager.add_turn("session_abc", "user", "Hello second")
    
    # Recall recent context
    results = await manager.recall("query is ignored in context mode", "session_abc", limit=2)
    
    assert len(results) == 2
    assert results[0]["content"] == "Response first"
    assert results[1]["content"] == "Hello second"
    assert results[0]["source"] == "context"
    
    manager.close()


@pytest.mark.asyncio
async def test_memory_manager_write_frequency_session(tmp_path):
    # Initialize in session write mode
    manager = MemoryManager(workspace=tmp_path, recall_mode="hybrid", write_frequency="session")
    
    # Add turns
    await manager.add_turn("session_xyz", "user", "Topic: bananas")
    
    # Check session buffer contains the turn doc
    assert len(manager.turn_buffers["session_xyz"]) == 1
    
    # Flush memory
    await manager.flush("session_xyz")
    
    # Buffer should now be cleared/popped
    assert "session_xyz" not in manager.turn_buffers
    
    manager.close()


@pytest.mark.asyncio
async def test_memory_manager_write_frequency_n_turns(tmp_path):
    # Initialize with N=3 write frequency
    manager = MemoryManager(workspace=tmp_path, recall_mode="hybrid", write_frequency=3)
    
    # Add 2 turns (should buffer)
    await manager.add_turn("session_123", "user", "First message")
    await manager.add_turn("session_123", "assistant", "Second message")
    assert len(manager.turn_buffers["session_123"]) == 2
    
    # Add 3rd turn (should trigger auto flush)
    await manager.add_turn("session_123", "user", "Third message")
    assert "session_123" not in manager.turn_buffers
    
    manager.close()


@pytest.mark.asyncio
async def test_memory_manager_tools_recall_mode(tmp_path):
    # Initialize with tools recall mode
    manager = MemoryManager(workspace=tmp_path, recall_mode="tools", write_frequency="turn")
    
    await manager.add_turn("session_789", "user", "Some input")
    
    # In tools recall mode, recall() should return empty list
    results = await manager.recall("Some", "session_789")
    assert results == []
    
    manager.close()
