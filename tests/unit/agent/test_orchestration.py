"""Unit tests for Hierarchical Agent Orchestration (specialized worker roles)."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from amberclaw.agent.subagent import SubagentManager


class MockAgentGraph:
    def __init__(self, provider, tools, max_iterations=15, mode="react"):
        self.provider = provider
        self.tools = tools
        self.max_iterations = max_iterations
        self.mode = mode
        self.runnable = AsyncMock()
        # Mock final state returned by LangGraph runnable.ainvoke
        mock_msg = MagicMock()
        mock_msg.content = "Task completed successfully"
        self.runnable.ainvoke.return_value = {
            "messages": [mock_msg],
        }


@pytest.mark.asyncio
async def test_subagent_orchestration_coder_role():
    provider = MagicMock()
    bus = AsyncMock()
    workspace = Path("/dummy/workspace")

    manager = SubagentManager(
        provider=provider,
        workspace=workspace,
        bus=bus,
        brave_api_key="fake-key",
    )

    with patch("amberclaw.agent.subagent.AgentGraph", side_effect=MockAgentGraph) as mock_graph_cls:
        await manager._run_subagent(
            task_id="test-coder",
            task="Write a python script",
            label="Coder Task",
            origin={"channel": "cli", "chat_id": "direct"},
            worker_role="coder",
        )

        mock_graph_cls.assert_called_once()
        called_args, called_kwargs = mock_graph_cls.call_args
        registered_tools = called_kwargs.get("tools") or called_args[1]

        registered_names = {t.name for t in registered_tools}
        assert "read_file" in registered_names
        assert "write_file" in registered_names
        assert "edit_file" in registered_names
        assert "list_dir" in registered_names
        assert "exec" in registered_names
        assert "web_search" not in registered_names
        assert "web_fetch" not in registered_names


@pytest.mark.asyncio
async def test_subagent_orchestration_researcher_role():
    provider = MagicMock()
    bus = AsyncMock()
    workspace = Path("/dummy/workspace")

    manager = SubagentManager(
        provider=provider,
        workspace=workspace,
        bus=bus,
        brave_api_key="fake-key",
    )

    with patch("amberclaw.agent.subagent.AgentGraph", side_effect=MockAgentGraph) as mock_graph_cls:
        await manager._run_subagent(
            task_id="test-researcher",
            task="Find the latest news",
            label="Researcher Task",
            origin={"channel": "cli", "chat_id": "direct"},
            worker_role="researcher",
        )

        mock_graph_cls.assert_called_once()
        called_args, called_kwargs = mock_graph_cls.call_args
        registered_tools = called_kwargs.get("tools") or called_args[1]

        registered_names = {t.name for t in registered_tools}
        assert "read_file" in registered_names
        assert "list_dir" in registered_names
        assert "web_search" in registered_names
        assert "web_fetch" in registered_names
        assert "write_file" not in registered_names
        assert "edit_file" not in registered_names
        assert "exec" not in registered_names


@pytest.mark.asyncio
async def test_subagent_orchestration_reader_role():
    provider = MagicMock()
    bus = AsyncMock()
    workspace = Path("/dummy/workspace")

    manager = SubagentManager(
        provider=provider,
        workspace=workspace,
        bus=bus,
    )

    with patch("amberclaw.agent.subagent.AgentGraph", side_effect=MockAgentGraph) as mock_graph_cls:
        await manager._run_subagent(
            task_id="test-reader",
            task="Read config file",
            label="Reader Task",
            origin={"channel": "cli", "chat_id": "direct"},
            worker_role="reader",
        )

        mock_graph_cls.assert_called_once()
        called_args, called_kwargs = mock_graph_cls.call_args
        registered_tools = called_kwargs.get("tools") or called_args[1]

        registered_names = {t.name for t in registered_tools}
        assert "read_file" in registered_names
        assert "list_dir" in registered_names
        assert "write_file" not in registered_names
        assert "edit_file" not in registered_names
        assert "exec" not in registered_names
        assert "web_search" not in registered_names
        assert "web_fetch" not in registered_names


@pytest.mark.asyncio
async def test_subagent_orchestration_general_role():
    provider = MagicMock()
    bus = AsyncMock()
    workspace = Path("/dummy/workspace")

    manager = SubagentManager(
        provider=provider,
        workspace=workspace,
        bus=bus,
        brave_api_key="fake-key",
    )

    with patch("amberclaw.agent.subagent.AgentGraph", side_effect=MockAgentGraph) as mock_graph_cls:
        await manager._run_subagent(
            task_id="test-general",
            task="Do everything",
            label="General Task",
            origin={"channel": "cli", "chat_id": "direct"},
            worker_role="general",
        )

        mock_graph_cls.assert_called_once()
        called_args, called_kwargs = mock_graph_cls.call_args
        registered_tools = called_kwargs.get("tools") or called_args[1]

        registered_names = {t.name for t in registered_tools}
        assert "read_file" in registered_names
        assert "write_file" in registered_names
        assert "edit_file" in registered_names
        assert "list_dir" in registered_names
        assert "exec" in registered_names
        assert "web_search" in registered_names
        assert "web_fetch" in registered_names
