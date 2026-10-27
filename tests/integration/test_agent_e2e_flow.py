# ruff: noqa: PLR2004, ARG002, PLR0913
"""Full End-to-End (E2E) integration test for AmberClaw Agent Loop.

Validates the full loop lifecycle:
1. Inbound message reception via MessageBus
2. System context and tool schema preparation
3. Provider invocation and ToolCallRequest parsing
4. Sandboxed execution of tool (Filesystem / Shell / etc.)
5. Feedback observation loop to LLM
6. OutboundMessage publication to MessageBus with correct correlation metadata
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from amberclaw.agent.loop import AgentLoop
from amberclaw.bus.events import InboundMessage, OutboundMessage
from amberclaw.bus.queue import MessageBus
from amberclaw.providers.base import LLMProvider, LLMResponse, ToolCallRequest


class MockLLMProvider(LLMProvider):
    """Mock LLM provider that simulates a 2-turn tool-calling conversation."""

    def __init__(self):
        super().__init__(api_key="mock-key", api_base="http://localhost")
        self.call_count = 0
        self.recorded_messages = []

    def get_default_model(self) -> str:
        return "mock-model"

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
        self.call_count += 1
        self.recorded_messages.append(list(messages))

        if self.call_count == 1:
            # Turn 1: LLM decides to create a file using write_file tool
            return LLMResponse(
                content="I will create the requested file for you.",
                tool_calls=[
                    ToolCallRequest(
                        id="call_write_1",
                        name="write_file",
                        arguments={
                            "path": "test_output.txt",
                            "content": "Hello from AmberClaw E2E Agent!",
                        },
                    )
                ],
                finish_reason="tool_calls",
                usage={"prompt_tokens": 50, "completion_tokens": 20},
            )

        # Turn 2: LLM receives tool result and produces final answer
        return LLMResponse(
            content="Successfully created test_output.txt with the requested text.",
            tool_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 80, "completion_tokens": 15},
        )


@pytest.mark.asyncio
async def test_agent_e2e_message_tool_response_flow(tmp_path: Path):
    """E2E Test: Inbound Message -> Tool Execution -> Outbound Message."""
    bus = MessageBus()
    provider = MockLLMProvider()
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()

    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=workspace_dir,
        restrict_to_workspace=True,
    )

    # Disable background mcp and external service connections for test isolation
    agent._connect_mcp = AsyncMock()

    # Step 1: Create and publish inbound user message
    inbound = InboundMessage(
        channel="telegram",
        sender_id="user_777",
        chat_id="chat_999",
        content="Please write 'Hello from AmberClaw E2E Agent!' to test_output.txt",
        metadata={"user_role": "admin", "session_id": "test_e2e_session"},
    )
    await bus.publish_inbound(inbound)

    # Step 2: Start agent loop worker in background
    agent_task = asyncio.create_task(agent.run())

    # Step 3: Wait for outbound messages to be published to the bus
    outbound_messages: list[OutboundMessage] = []
    for _ in range(50):
        while bus.outbound_size > 0:
            msg = await bus.consume_outbound()
            outbound_messages.append(msg)
        if any(
            "Successfully created test_output.txt" in m.content
            for m in outbound_messages
        ):
            break
        await asyncio.sleep(0.1)

    # Step 4: Stop agent
    agent.stop()
    await agent_task

    # Step 5: Verify E2E assertions
    assert outbound_messages, "Agent did not produce outbound response within timeout"
    final_response = outbound_messages[-1]
    assert final_response.channel == "telegram"
    assert final_response.chat_id == "chat_999"
    assert "Successfully created test_output.txt" in final_response.content

    # Step 6: Verify actual tool side-effect in the sandboxed workspace
    created_file = workspace_dir / "test_output.txt"
    assert created_file.exists(), (
        "Target file was not created by the agent's tool execution"
    )
    assert created_file.read_text(encoding="utf-8") == "Hello from AmberClaw E2E Agent!"

    # Step 7: Verify conversation turns and message flow
    assert provider.call_count == 2, f"Expected 2 LLM turns, got {provider.call_count}"
