import pytest
from pathlib import Path
from amberclaw.memory.sqlite_memory import SQLiteMemoryManager


def test_sqlite_memory_manager_persistence_and_fts(tmp_path: Path):
    db_file = tmp_path / "test_sessions.db"
    mem_mgr1 = SQLiteMemoryManager(db_path=db_file)

    # Save conversation turns
    turn1_id = mem_mgr1.save_turn(
        session_id="sess_alpha",
        role="user",
        content="What is AmberClaw AI OS?",
        user_id="user_1",
    )
    turn2_id = mem_mgr1.save_turn(
        session_id="sess_alpha",
        role="assistant",
        content="AmberClaw is an open, self-hosted zero-trust AI agent runtime.",
        agent_id="agent_1",
    )

    assert turn1_id is not None
    assert turn2_id is not None

    # Retrieve history
    history = mem_mgr1.get_history(session_id="sess_alpha")
    assert len(history) == 2
    assert history[0]["content"] == "What is AmberClaw AI OS?"
    assert history[1]["content"] == "AmberClaw is an open, self-hosted zero-trust AI agent runtime."

    # Full-Text Search (FTS5)
    search_results = mem_mgr1.search_history(query="zero-trust", session_id="sess_alpha")
    assert len(search_results) == 1
    assert search_results[0]["role"] == "assistant"

    mem_mgr1.close()

    # Re-open in new instance (simulating restart)
    mem_mgr2 = SQLiteMemoryManager(db_path=db_file)
    reloaded_history = mem_mgr2.get_history(session_id="sess_alpha")
    assert len(reloaded_history) == 2
    assert reloaded_history[0]["content"] == "What is AmberClaw AI OS?"
    mem_mgr2.close()
