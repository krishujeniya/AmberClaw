"""Unit tests for the Autonomous Skill Creator."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from amberclaw.agent.learning.skill_creator import SkillCreator


@pytest.mark.asyncio
async def test_skill_creator_below_threshold(tmp_path: Path):
    mock_provider = MagicMock()
    creator = SkillCreator(mock_provider, tmp_path)

    # 2 assistant turns, 2 tool calls -> below threshold
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi", "tool_calls": [{"name": "tool1"}]},
        {"role": "tool", "content": "result"},
        {"role": "assistant", "content": "done", "tool_calls": [{"name": "tool2"}]},
        {"role": "tool", "content": "result"},
    ]

    path = await creator.monitor_and_create(messages)
    assert path is None
    mock_provider.chat_with_retry.assert_not_called()


@pytest.mark.asyncio
async def test_skill_creator_above_turns_threshold(tmp_path: Path):
    mock_provider = MagicMock()
    mock_response = MagicMock()
    mock_response.content = (
        "---\n"
        "name: test-skill\n"
        "description: A test skill\n"
        "---\n"
        "# Skill: Test Skill\n"
        "## Steps\n1. Do something\n"
    )
    mock_provider.chat_with_retry = AsyncMock(return_value=mock_response)

    # 4 assistant turns -> above turns threshold (> 3)
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "1"},
        {"role": "assistant", "content": "2"},
        {"role": "assistant", "content": "3"},
        {"role": "assistant", "content": "4"},
    ]

    # Mock Path.home() to return a temp directory to avoid polluting user's real home
    fake_home = tmp_path / "home"
    with patch("pathlib.Path.home", return_value=fake_home):
        creator = SkillCreator(mock_provider, tmp_path)
        path = await creator.monitor_and_create(messages)

        assert path is not None
        assert path.name == "test-skill.md"
        assert path.exists()

        # Check global path content
        content = path.read_text(encoding="utf-8")
        assert "name: test-skill" in content

        # Check workspace path content
        workspace_path = tmp_path / "skills" / "auto-created" / "test-skill" / "SKILL.md"
        assert workspace_path.exists()
        assert workspace_path.read_text(encoding="utf-8") == content


@pytest.mark.asyncio
async def test_skill_creator_above_tools_threshold(tmp_path: Path):
    mock_provider = MagicMock()
    mock_response = MagicMock()
    mock_response.content = (
        "---\n"
        "name: many-tools-skill\n"
        "description: Skill with many tools\n"
        "---\n"
        "# Skill: Many Tools\n"
    )
    mock_provider.chat_with_retry = MagicMock()
    mock_provider.chat_with_retry.chat_with_retry = AsyncMock() # compatibility with mock
    mock_provider.chat_with_retry = AsyncMock(return_value=mock_response)

    # 2 assistant turns but 6 tool calls -> above tools threshold (> 5)
    messages = [
        {"role": "user", "content": "hello"},
        {
            "role": "assistant",
            "content": "1",
            "tool_calls": [{"name": "t1"}, {"name": "t2"}, {"name": "t3"}],
        },
        {"role": "tool", "content": "res"},
        {
            "role": "assistant",
            "content": "2",
            "tool_calls": [{"name": "t4"}, {"name": "t5"}, {"name": "t6"}],
        },
    ]

    fake_home = tmp_path / "home"
    with patch("pathlib.Path.home", return_value=fake_home):
        creator = SkillCreator(mock_provider, tmp_path)
        path = await creator.monitor_and_create(messages)

        assert path is not None
        assert path.name == "many-tools-skill.md"
        assert path.exists()
