
# ruff: noqa: PLR2004
import pytest

from amberclaw.memory.base import ScopeContext
from amberclaw.memory.manager import MemoryManager
from amberclaw.memory.session_db import SessionDB


def test_session_db_multi_scope_writes_and_reads(tmp_path):
    db_file = tmp_path / "sessions.db"
    db = SessionDB(db_file)

    # 1. Add turns with different scopes
    db.add_turn(
        session_id="sess-1",
        role="user",
        content="Turn 1: User 1 Org 1",
        user_id="user-1",
        agent_id="agent-1",
        org_id="org-1",
    )
    db.add_turn(
        session_id="sess-2",
        role="assistant",
        content="Turn 2: User 1 Org 1",
        user_id="user-1",
        agent_id="agent-1",
        org_id="org-1",
    )
    db.add_turn(
        session_id="sess-3",
        role="user",
        content="Turn 3: User 2 Org 1",
        user_id="user-2",
        agent_id="agent-1",
        org_id="org-1",
    )
    db.add_turn(
        session_id="sess-4",
        role="user",
        content="Turn 4: User 2 Org 2",
        user_id="user-2",
        agent_id="agent-2",
        org_id="org-2",
    )

    # 2. Test exact match query (hierarchical=False)
    turns_user1 = db.get_turns(user_id="user-1")
    assert len(turns_user1) == 2
    assert "Turn 1" in turns_user1[0]["content"]
    assert "Turn 2" in turns_user1[1]["content"]

    turns_exact = db.get_turns(user_id="user-1", session_id="sess-1")
    assert len(turns_exact) == 1
    assert "Turn 1" in turns_exact[0]["content"]

    # 3. Test hierarchical OR query (hierarchical=True)
    # Get all turns for either sess-1 OR user-2
    turns_hierarchical = db.get_turns(
        session_id="sess-1", user_id="user-2", hierarchical=True
    )
    assert len(turns_hierarchical) == 3  # Turn 1, Turn 3, Turn 4
    contents = [t["content"] for t in turns_hierarchical]
    assert "Turn 1: User 1 Org 1" in contents
    assert "Turn 3: User 2 Org 1" in contents
    assert "Turn 4: User 2 Org 2" in contents

    # 4. Test FTS search with scope filters
    # Search "User" within org-2
    results_fts_org2 = db.search_turns(query="User", org_id="org-2")
    assert len(results_fts_org2) == 1
    assert "Turn 4" in results_fts_org2[0]["content"]

    # Search "User" within org-1 OR sess-4 hierarchically
    results_fts_hierarchical = db.search_turns(
        query="User", org_id="org-1", session_id="sess-4", hierarchical=True
    )
    assert len(results_fts_hierarchical) == 4  # Turn 1, Turn 2, Turn 3 (org-1) + Turn 4 (sess-4)

    db.close()


@pytest.mark.asyncio
async def test_memory_manager_scope_context(tmp_path):
    # Initialize MemoryManager in context mode to test retrieval behavior
    manager = MemoryManager(workspace=tmp_path, recall_mode="context")

    scope = ScopeContext(
        user_id="user-a",
        agent_id="agent-b",
        session_id="session-c",
        org_id="org-d",
    )

    await manager.add_turn(
        session_id="session-c",
        role="user",
        content="Scoped message content",
        scope_context=scope,
    )

    # Test retrieving via recall
    results = await manager.recall(
        query="",
        scope_context=scope,
        limit=5,
    )
    assert len(results) == 1
    assert results[0]["content"] == "Scoped message content"
    assert results[0]["metadata"]["user_id"] == "user-a"
    assert results[0]["metadata"]["agent_id"] == "agent-b"
    assert results[0]["metadata"]["org_id"] == "org-d"

    # Test isolation: recall for a different scope should return nothing
    other_scope = ScopeContext(
        user_id="user-x",
        agent_id="agent-y",
        session_id="session-z",
        org_id="org-w",
    )
    results_empty = await manager.recall(
        query="",
        scope_context=other_scope,
        limit=5,
    )
    assert len(results_empty) == 0
