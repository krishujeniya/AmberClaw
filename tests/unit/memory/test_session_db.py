# ruff: noqa: PLR2004
"""Unit tests for the SQLite Session Database system (WAL + FTS5)."""


from amberclaw.memory.session_db import SessionDB


def test_session_db_initialization_and_wal(tmp_path):
    db_file = tmp_path / "sessions.db"
    db = SessionDB(db_file)
    
    # Assert WAL journal mode is active
    cursor = db.conn.execute("PRAGMA journal_mode;")
    mode = cursor.fetchone()[0]
    assert mode.lower() == "wal"
    
    db.close()


def test_session_db_add_and_retrieve_turns(tmp_path):
    db_file = tmp_path / "sessions.db"
    db = SessionDB(db_file)
    
    # Test auto-incrementing turn indices
    id1 = db.add_turn(session_id="session_1", role="user", content="Hello, AmberClaw!")
    id2 = db.add_turn(session_id="session_1", role="assistant", content="Hi there!")
    id3 = db.add_turn(session_id="session_1", role="user", content="Tell me a joke.")
    
    assert id1 is not None
    assert id2 is not None
    assert id3 is not None

    turns = db.get_turns("session_1")
    assert len(turns) == 3
    assert turns[0]["turn_index"] == 0
    assert turns[1]["turn_index"] == 1
    assert turns[2]["turn_index"] == 2
    
    assert turns[0]["content"] == "Hello, AmberClaw!"
    assert turns[1]["role"] == "assistant"
    
    db.close()


def test_session_db_fts5_search_and_triggers(tmp_path):
    db_file = tmp_path / "sessions.db"
    db = SessionDB(db_file)
    
    # Add turns to search
    db.add_turn(
        session_id="session_1",
        role="user",
        content="The quick brown fox jumps over the lazy dog.",
    )
    db.add_turn(
        session_id="session_1",
        role="assistant",
        content="I love eating red apples and bananas.",
    )
    db.add_turn(
        session_id="session_2",
        role="user",
        content="The brown fox is really quick today.",
    )
    
    # Match search term
    results_fox = db.search_turns("fox")
    assert len(results_fox) == 2
    assert results_fox[0]["content"] == "The brown fox is really quick today."
    
    # Filter search by session
    results_fox_s1 = db.search_turns("fox", session_id="session_1")
    assert len(results_fox_s1) == 1
    assert "lazy dog" in results_fox_s1[0]["content"]
    
    # Test update trigger sync
    turn_to_update = results_fox[0]["id"]
    db.update_turn_content(turn_to_update, "The lazy cat sleeps all day.")
    
    # Verify search matches updated content and no longer matches old content
    results_updated = db.search_turns("cat")
    assert len(results_updated) == 1
    assert results_updated[0]["id"] == turn_to_update
    
    results_stale = db.search_turns("fox")
    assert len(results_stale) == 1  # Only session_1's turn has 'fox' now
    
    # Test delete trigger sync
    db.delete_turn(turn_to_update)
    results_deleted = db.search_turns("cat")
    assert len(results_deleted) == 0
    
    db.close()
