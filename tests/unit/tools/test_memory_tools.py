# ruff: noqa: E501
"""Unit tests for AmberClaw Memory Agent Tools."""

import uuid

import pytest

from amberclaw.memory.manager import memory
from amberclaw.tools.memory_tools import (
    ForgetTool,
    RecallTool,
    RememberTool,
    SessionSearchTool,
    SummarizeSessionTool,
)


@pytest.mark.asyncio
async def test_remember_tool():
    tool = RememberTool()
    res = await tool.run(fact="The user prefers Python", entity="user", entity_type="Person")
    assert "Successfully remembered fact" in res
    assert "The user prefers Python" in res
    assert "user" in res


@pytest.mark.asyncio
async def test_recall_tool():
    session_id = f"test_session_{uuid.uuid4().hex}"
    # Insert a mock turn into session_db or inject to memories to make it recallable
    memory.session_db.add_turn(
        session_id=session_id,
        role="assistant",
        content="I am recalling Python details.",
    )

    tool = RecallTool()
    res = await tool.run(query="Python", session_id=session_id)
    assert res is not None


@pytest.mark.asyncio
async def test_forget_tool():
    tool = ForgetTool()
    res = await tool.run(query="forget me")
    assert "forget" in res


@pytest.mark.asyncio
async def test_session_search_tool():
    session_id = f"test_session_{uuid.uuid4().hex}"
    memory.session_db.add_turn(
        session_id=session_id,
        role="user",
        content="I love debugging code",
    )

    tool = SessionSearchTool()
    res = await tool.run(session_id=session_id, query="debugging")
    assert "user" in res
    assert "debugging" in res


@pytest.mark.asyncio
async def test_summarize_session_tool():
    session_id = f"test_session_{uuid.uuid4().hex}"
    memory.session_db.add_turn(
        session_id=session_id,
        role="user",
        content="Hello!",
    )
    memory.session_db.add_turn(
        session_id=session_id,
        role="assistant",
        content="How can I help you?",
    )

    tool = SummarizeSessionTool()
    res = await tool.run(session_id=session_id)
    assert "Total turns: 2" in res
    assert "Hello!" in res
