"""Test scratch_pad parsing, isolation, and re-injection in AgentGraph."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from amberclaw.agent.graph import AgentGraph, AgentState
from amberclaw.agent.loop import AgentLoop
from amberclaw.bus.events import InboundMessage
from amberclaw.bus.queue import MessageBus
from amberclaw.providers.base import LLMResponse


def _make_loop(tmp_path: Path) -> AgentLoop:
    bus = MessageBus()
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    return AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        memory_window=10,
    )


@pytest.mark.asyncio
async def test_scratch_pad_isolated_and_logged(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path)
    response_content = (
        "<scratch_pad>\nGoal: Test the scratchpad\n"
        "Reflection: Validated\n</scratch_pad>\nHello there!"
    )
    loop.provider.chat_with_retry = AsyncMock(
        return_value=LLMResponse(
            content=response_content,
            tool_calls=[],
        ),
    )
    loop.tools.get_definitions = MagicMock(return_value=[])

    msg = InboundMessage(
        channel="feishu",
        sender_id="user1",
        chat_id="chat123",
        content="Hi",
    )
    result = await loop._process_message(msg)

    assert result is not None
    # Verify the output message does NOT contain the scratch_pad tag
    assert "<scratch_pad>" not in result.content
    assert "</scratch_pad>" not in result.content
    assert "Hello there!" in result.content


@pytest.mark.asyncio
async def test_scratch_pad_reinjected_into_history() -> None:
    # Test directly that _call_llm_with_state re-injects the scratchpad
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    provider.chat_with_retry = AsyncMock(
        return_value=LLMResponse(
            content="Success response",
            tool_calls=[],
        ),
    )
    graph = AgentGraph(provider=provider, tools=[])

    # Construct messages where assistant message has scratch_pad in additional_kwargs
    assistant_msg = AIMessage(content="Final reply content")
    assistant_msg.additional_kwargs["scratch_pad"] = (
        "Goal: Plan stuff\nActions: Do stuff"
    )

    state = AgentState(
        messages=[
            HumanMessage(content="User input"),
            assistant_msg,
        ],
        iterations=0,
        config={
            "model": "test-model",
            "llm_kwargs": {},
        },
        mode="react",
        plan=[],
        current_task=None,
    )

    await graph._call_llm_with_state(state)

    # Inspect messages that were actually sent to the mock LLM
    called_args, called_kwargs = provider.chat_with_retry.call_args
    sent_messages = called_kwargs.get("messages") or called_args[0]

    # Verify that the assistant message sent has re-injected the scratch_pad
    assistant_sent = next(m for m in sent_messages if m["role"] == "assistant")
    assert "<scratch_pad>" in assistant_sent["content"]
    assert "Goal: Plan stuff" in assistant_sent["content"]
    assert "Final reply content" in assistant_sent["content"]
