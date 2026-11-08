"""Regression checks for messages delivered to the base agent callback."""

from collections.abc import Iterator

import pytest
from loguru import logger

from amberclaw.agent import core
from amberclaw.core.networking import AgentMessage, AgentNetworking


@pytest.fixture
def received_logs() -> Iterator[list[str]]:
    """Capture real delivery logs, including failures swallowed by networking."""
    messages: list[str] = []
    sink_id = logger.add(messages.append, format="{level.name}: {message}")
    try:
        yield messages
    finally:
        logger.remove(sink_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("delivery", ["callback", "direct", "broadcast"])
async def test_base_agent_receives_network_message(
    monkeypatch: pytest.MonkeyPatch, received_logs: list[str], delivery: str
) -> None:
    """Delivery must reach the default handler without a hidden NameError."""
    networking = AgentNetworking()
    monkeypatch.setattr(core, "network", networking)
    agent = core.BaseAgent(id="recipient", name="Recipient")
    message = AgentMessage(
        sender_id="sender",
        receiver_id="recipient" if delivery == "direct" else None,
        topic="task.ready",
    )

    if delivery == "callback":
        await agent.handle_agent_message(message)
    else:
        networking.subscribe(agent.id, message.topic)
        await networking.send(message)

    assert any(
        "Agent recipient received message from sender on topic task.ready" in entry
        for entry in received_logs
    )
    assert not any("ERROR:" in entry for entry in received_logs)
    assert not agent.state.is_busy
