# ruff: noqa: PLR2004
"""Unit tests for AmberClaw SubagentManager, role specialization, and lifecycle."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from amberclaw.agent.subagent import SubagentManager
from amberclaw.bus.queue import MessageBus
from amberclaw.providers.base import LLMProvider, LLMResponse


class DummyProvider(LLMProvider):
    """Deterministic mock provider for subagent execution tests."""

    def __init__(self, default_response: str = "Subagent task completed."):
        self.default_response = default_response
        self.invocations: list[dict] = []

    def get_default_model(self) -> str:
        return "mock-llm-v1"

    async def chat(self, messages, **kwargs) -> LLMResponse:
        self.invocations.append({"messages": messages, "kwargs": kwargs})
        return LLMResponse(content=self.default_response)


@pytest.fixture
def mock_bus() -> MessageBus:
    bus = MessageBus()
    bus.publish_inbound = AsyncMock()
    return bus


# ==============================================================================
# 1. Role Prompt Specialization
# ==============================================================================


def test_subagent_role_prompt_specialization(tmp_path: Path, mock_bus: MessageBus):
    provider = DummyProvider()
    mgr = SubagentManager(
        provider=provider,
        workspace=tmp_path,
        bus=mock_bus,
    )

    coder_prompt = mgr._build_subagent_prompt(role="coder")
    assert "Role: CODER" in coder_prompt
    assert "read, write, edit, and execute code" in coder_prompt

    researcher_prompt = mgr._build_subagent_prompt(role="researcher")
    assert "Role: RESEARCHER" in researcher_prompt
    assert "perform web search and fetch resources" in researcher_prompt
    assert "read-only" in researcher_prompt or "do not have write" in researcher_prompt

    reader_prompt = mgr._build_subagent_prompt(role="reader")
    assert "Role: READER" in reader_prompt
    assert "safe, read-only mode" in reader_prompt


# ==============================================================================
# 2. Spawning & Running Count
# ==============================================================================


@pytest.mark.asyncio
async def test_subagent_spawn_and_tracking(tmp_path: Path, mock_bus: MessageBus):
    provider = DummyProvider()
    mgr = SubagentManager(
        provider=provider,
        workspace=tmp_path,
        bus=mock_bus,
    )

    # Spawn subagent task
    msg = await mgr.spawn(
        task="Summarize repo architecture",
        label="arch-summary",
        origin_channel="slack",
        origin_chat_id="C12345",
        session_key="session_alpha",
        worker_role="researcher",
    )

    assert "Subagent [arch-summary] started" in msg
    assert "id:" in msg
    assert mgr.get_running_count() <= 1


# ==============================================================================
# 3. Session Cancellation
# ==============================================================================


@pytest.mark.asyncio
async def test_subagent_cancel_by_session(tmp_path: Path, mock_bus: MessageBus):
    provider = DummyProvider()
    mgr = SubagentManager(
        provider=provider,
        workspace=tmp_path,
        bus=mock_bus,
    )

    # Mock _run_subagent to run indefinitely until cancelled
    async def infinite_subagent(*_args, **_kwargs):
        await asyncio.sleep(10.0)

    mgr._run_subagent = infinite_subagent

    await mgr.spawn(
        task="Long running analysis 1",
        session_key="session_to_cancel",
    )
    await mgr.spawn(
        task="Long running analysis 2",
        session_key="session_to_cancel",
    )
    await mgr.spawn(
        task="Unaffected task",
        session_key="session_keep",
    )

    assert mgr.get_running_count() == 3

    cancelled_count = await mgr.cancel_by_session("session_to_cancel")
    assert cancelled_count == 2
    assert mgr.get_running_count() == 1

    # Clean up remaining
    await mgr.cancel_by_session("session_keep")
    assert mgr.get_running_count() == 0


# ==============================================================================
# 4. Result Announcement on Message Bus
# ==============================================================================


@pytest.mark.asyncio
async def test_subagent_announce_result_success(tmp_path: Path, mock_bus: MessageBus):
    provider = DummyProvider()
    mgr = SubagentManager(
        provider=provider,
        workspace=tmp_path,
        bus=mock_bus,
    )

    origin = {"channel": "telegram", "chat_id": "tg_987"}
    await mgr._announce_result(
        task_id="task_123",
        label="benchmark",
        task="Run latency test",
        result="Average latency is 12ms",
        origin=origin,
        status="ok",
    )

    assert mock_bus.publish_inbound.called
    published_msg = mock_bus.publish_inbound.call_args[0][0]
    assert published_msg.channel == "system"
    assert published_msg.chat_id == "telegram:tg_987"
    assert "completed successfully" in published_msg.content
    assert "Average latency is 12ms" in published_msg.content


@pytest.mark.asyncio
async def test_subagent_announce_result_error(tmp_path: Path, mock_bus: MessageBus):
    provider = DummyProvider()
    mgr = SubagentManager(
        provider=provider,
        workspace=tmp_path,
        bus=mock_bus,
    )

    origin = {"channel": "cli", "chat_id": "direct"}
    await mgr._announce_result(
        task_id="task_456",
        label="failing_task",
        task="Execute malformed bash script",
        result="Error: Permission denied",
        origin=origin,
        status="error",
    )

    assert mock_bus.publish_inbound.called
    published_msg = mock_bus.publish_inbound.call_args[0][0]
    assert "failed" in published_msg.content
    assert "Permission denied" in published_msg.content
