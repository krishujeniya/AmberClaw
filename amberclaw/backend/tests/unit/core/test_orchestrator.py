"""Offline compatibility and lifecycle checks for the orchestration adapter."""

import asyncio
from types import SimpleNamespace

import pytest

from amberclaw.bus.events import InboundMessage, OutboundMessage
from amberclaw.bus.queue import MessageBus
from amberclaw.channels.base import BaseChannel
from amberclaw.channels.manager import ChannelManager
from amberclaw.config.schema import Config
from amberclaw.core.orchestrator import Orchestrator
from amberclaw.models.message import Message, MessageRole


class EchoAgent:
    """Consume the real bus without a provider or external service."""

    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus
        self.closed = False
        self.stopped = False

    async def run(self) -> None:
        while True:
            message = await self.bus.consume_inbound()
            await self.bus.publish_outbound(
                OutboundMessage(
                    channel=message.channel,
                    chat_id=message.chat_id,
                    content=f"echo:{message.content}",
                    metadata=message.metadata,
                )
            )

    def stop(self) -> None:
        self.stopped = True

    async def close_mcp(self) -> None:
        self.closed = True


class RecordingChannel(BaseChannel):
    """Use the production channel manager with in-memory channel I/O."""

    def __init__(self, name: str, bus: MessageBus) -> None:
        super().__init__(SimpleNamespace(allow_from=["tester"]), bus)
        self.name = name
        self.sent: asyncio.Queue[OutboundMessage] = asyncio.Queue()
        self.finished = asyncio.Event()

    async def start(self) -> None:
        self._running = True
        await self.finished.wait()

    async def stop(self) -> None:
        self._running = False
        self.finished.set()

    async def send(self, msg: OutboundMessage) -> None:
        await self.sent.put(msg)


@pytest.mark.asyncio
@pytest.mark.parametrize("channel_name", ["telegram", "discord"])
async def test_legacy_message_roundtrip_and_shutdown(channel_name: str) -> None:
    bus = MessageBus()
    agent = EchoAgent(bus)
    manager = ChannelManager(Config(), bus)
    channel = RecordingChannel(channel_name, bus)
    manager.channels[channel_name] = channel
    orchestrator = Orchestrator(agent=agent, channels=manager)

    await orchestrator.start()
    await orchestrator.start()  # Idempotent; no duplicate bus consumers.
    try:
        original = Message(
            role=MessageRole.USER,
            content="hello",
            metadata={
                "channel_name": channel_name,
                "user_id": "tester",
                "chat_id": "room" if channel_name == "telegram" else None,
                "channel_id": "room" if channel_name == "discord" else None,
                "correlation_id": "request-1",
            },
        )
        await orchestrator.handle_inbound_message(original)
        response = await asyncio.wait_for(channel.sent.get(), timeout=2)
        assert response.content == "echo:hello"
        assert response.channel == channel_name
        assert response.chat_id == "room"
        assert response.metadata["correlation_id"] == "request-1"
    finally:
        await orchestrator.stop()
        await orchestrator.stop()
    assert agent.stopped and agent.closed
    assert not channel.is_running
    assert not orchestrator._running_tasks
    assert manager._dispatch_task is None or manager._dispatch_task.done()


@pytest.mark.asyncio
async def test_native_bus_message_and_invalid_legacy_routing() -> None:
    bus = MessageBus()
    manager = ChannelManager(Config(), bus)
    channel = RecordingChannel("telegram", bus)
    manager.channels[channel.name] = channel
    orchestrator = Orchestrator(agent=EchoAgent(bus), channels=manager)
    await orchestrator.start()
    try:
        await orchestrator.handle_inbound_message(
            InboundMessage("telegram", "tester", "native", "hello")
        )
        response = await asyncio.wait_for(channel.sent.get(), timeout=2)
        assert response.chat_id == "native"
        for metadata in [
            {},
            {"channel_name": "unknown", "user_id": "tester", "chat_id": "room"},
            {"channel_name": "telegram", "user_id": "tester"},
        ]:
            with pytest.raises(ValueError):
                await orchestrator.handle_inbound_message(
                    Message(role=MessageRole.USER, content="reject", metadata=metadata)
                )
        with pytest.raises(ValueError, match="user"):
            await orchestrator.handle_inbound_message(
                Message(role=MessageRole.SYSTEM, content="reject")
            )
        assert bus.inbound_size == 0
    finally:
        await orchestrator.stop()


@pytest.mark.asyncio
async def test_requires_configured_runtime_and_shared_bus() -> None:
    orchestrator = Orchestrator()
    with pytest.raises(RuntimeError, match="configure"):
        await orchestrator.start()
    with pytest.raises(RuntimeError, match="running"):
        await orchestrator.handle_inbound_message(
            InboundMessage("telegram", "tester", "room", "reject")
        )
    with pytest.raises(ValueError, match=r"same.*bus"):
        Orchestrator(
            agent=EchoAgent(MessageBus()),
            channels=ChannelManager(Config(), MessageBus()),
        )


@pytest.mark.asyncio
async def test_start_failure_drains_all_tasks() -> None:
    class FailingAgent(EchoAgent):
        async def run(self) -> None:
            raise RuntimeError("startup failed")

    bus = MessageBus()
    agent = FailingAgent(bus)
    manager = ChannelManager(Config(), bus)
    orchestrator = Orchestrator(agent=agent, channels=manager)
    with pytest.raises(RuntimeError, match="startup failed"):
        await orchestrator.start()
    assert agent.closed and agent.stopped
    assert not orchestrator._running_tasks
