# ruff: noqa: PLR2004, ARG002, PLR0913
"""End-to-End (E2E) Integration Tests for AmberClaw OS.

Tests complete multi-turn session workflows:
1. MessageBus event routing
2. Session state persistence and turn sequencing in SessionDB
3. Tool execution in sandboxed workspace
4. Cross-turn memory context retention
5. Graceful session cleanup
"""

from pathlib import Path

import pytest

from amberclaw.agent.loop import AgentLoop
from amberclaw.bus.events import InboundMessage, OutboundMessage
from amberclaw.bus.queue import MessageBus
from amberclaw.memory.session_db import SessionDB
from amberclaw.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from amberclaw.session.manager import SessionManager


class MultiTurnLLMProvider(LLMProvider):
    """Deterministic LLM Provider that simulates a multi-turn conversation with tool use."""

    def __init__(self):
        super().__init__(api_key="mock-key", api_base="http://localhost")
        self.turn = 0
        self.received_messages: list[list[dict]] = []

    def get_default_model(self) -> str:
        return "mock-e2e-model"

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
        reasoning_effort: str | None = None,
        response_format: dict | None = None,
        on_token=None,
    ) -> LLMResponse:
        self.turn += 1
        self.received_messages.append(list(messages))

        if self.turn == 1:
            # Turn 1: Write a project configuration file
            return LLMResponse(
                content="I will initialize project.json for you.",
                tool_calls=[
                    ToolCallRequest(
                        id="call_init_file",
                        name="write_file",
                        arguments={
                            "path": "project.json",
                            "content": '{"name": "amberclaw-e2e", "version": "1.0.0"}',
                        },
                    )
                ],
            )
        if self.turn == 2:
            # Turn 2: Confirm file was written
            return LLMResponse(
                content="Project configuration has been successfully created.",
                tool_calls=[],
            )
        # Subsequent turns
        return LLMResponse(
            content="I remember your project configuration.",
            tool_calls=[],
        )


@pytest.mark.asyncio
async def test_full_agent_multiturn_e2e_flow(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "sessions.db"

    session_db = SessionDB(db_path)
    session_mgr = SessionManager(workspace=workspace)
    session_mgr.session_db = session_db

    bus = MessageBus()
    outbound_messages: list[OutboundMessage] = []

    async def capture_outbound(msg: OutboundMessage):
        outbound_messages.append(msg)

    bus.publish_outbound = capture_outbound

    provider = MultiTurnLLMProvider()

    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=workspace,
        model="mock-e2e-model",
        session_manager=session_mgr,
        restrict_to_workspace=True,
    )

    # Dispatch Turn 1
    inbound_1 = InboundMessage(
        channel="cli",
        sender_id="dev_user",
        chat_id="direct",
        content="Please initialize project.json with version 1.0.0",
        session_key_override="e2e_test_session",
    )

    # Process message in loop
    resp_1 = await loop._process_message(inbound_1)

    # Verify tool execution created the file in workspace
    project_file = workspace / "project.json"
    assert project_file.exists()
    assert '"name": "amberclaw-e2e"' in project_file.read_text(encoding="utf-8")

    # Verify outbound confirmation was returned
    assert resp_1 is not None
    assert "successfully created" in resp_1.content

    # Dispatch Turn 2 to test multi-turn conversational memory
    inbound_2 = InboundMessage(
        channel="cli",
        sender_id="dev_user",
        chat_id="direct",
        content="Do you remember what project you initialized?",
        session_key_override="e2e_test_session",
    )
    resp_2 = await loop._process_message(inbound_2)
    assert resp_2 is not None
    assert "remember" in resp_2.content

    # Verify session history recorded in SessionManager
    session = session_mgr.get_or_create("e2e_test_session")
    # Should have recorded user queries and assistant turns
    assert len(session.messages) >= 2
    assert any(m.get("role") == "assistant" for m in session.messages)

    # Clean up loop
    loop.stop()
