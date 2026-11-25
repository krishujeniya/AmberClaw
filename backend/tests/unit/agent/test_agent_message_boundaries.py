"""Characterize graph conversion and persisted content before helper extraction."""

from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from amberclaw.agent.context import ContextBuilder
from amberclaw.agent.graph import AgentState
from amberclaw.agent.loop import AgentLoop
from amberclaw.session.manager import Session


async def test_graph_message_conversion_and_final_state(tmp_path: Path) -> None:
    observed: list[AgentState] = []

    async def stream(
        inputs: AgentState, **_kwargs: object
    ) -> AsyncIterator[AgentState]:
        observed.append(inputs)
        yield {
            **inputs,
            "messages": [*inputs["messages"], AIMessage(content="finished")],
        }

    agent = AgentLoop.__new__(AgentLoop)
    agent.workspace = tmp_path
    agent.mode = "react"
    agent.model = "offline"
    agent.temperature = 0.5
    agent.max_tokens = 50
    agent.reasoning_effort = None
    agent.fallback_models = []
    agent._graph = SimpleNamespace(runnable=SimpleNamespace(astream=stream))
    history: list[dict[str, Any]] = [
        {"role": "system", "content": "existing conversion omits system"},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "working", "scratch_pad": "private"},
        {"role": "tool", "content": "result", "tool_call_id": "call-1"},
    ]
    content, tools, messages = await agent._run_agent_loop(history)
    assert content == "finished"
    assert tools == ["tool"]
    assert [type(m) for m in observed[0]["messages"]] == [
        HumanMessage,
        AIMessage,
        ToolMessage,
    ]
    assert messages[1]["scratch_pad"] == "private"
    assert messages[2]["tool_call_id"] == "call-1"
    assert [m["role"] for m in messages] == ["user", "assistant", "tool", "assistant"]


def test_save_turn_filters_runtime_and_inline_images() -> None:
    agent = AgentLoop.__new__(AgentLoop)
    session = Session("test:session")
    agent._save_turn(
        session,
        [
            {"role": "assistant", "content": ""},
            {
                "role": "user",
                "content": f"{ContextBuilder._RUNTIME_CONTEXT_TAG}\n\nactual text",
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": ContextBuilder._RUNTIME_CONTEXT_TAG},
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,A"},
                    },
                    {"type": "text", "text": "caption"},
                ],
            },
        ],
        0,
    )
    assert [m["content"] for m in session.messages] == [
        "actual text",
        [{"type": "text", "text": "[image]"}, {"type": "text", "text": "caption"}],
    ]
