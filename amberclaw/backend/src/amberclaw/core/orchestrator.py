"""Application adapter for the canonical bus-driven agent and channel runtimes."""

from __future__ import annotations

import asyncio
from typing import Protocol

from loguru import logger

from amberclaw.bus.events import InboundMessage
from amberclaw.bus.queue import MessageBus
from amberclaw.models.message import Message, MessageRole


class AgentRuntime(Protocol):
    """Agent lifecycle required by the adapter; implemented by AgentLoop."""

    bus: MessageBus

    async def run(self) -> None:
        """Consume messages until stopped or cancelled."""
        ...

    def stop(self) -> None:
        """Request shutdown."""
        ...

    async def close_mcp(self) -> None:
        """Close external tool connections."""
        ...


class ChannelRuntime(Protocol):
    """Channel manager lifecycle and routing inventory."""

    bus: MessageBus

    @property
    def enabled_channels(self) -> list[str]:
        """Names of configured channel adapters."""
        ...

    async def start_all(self) -> None:
        """Run configured listeners and outbound dispatch."""
        ...

    async def stop_all(self) -> None:
        """Stop listeners and outbound dispatch."""
        ...


class Orchestrator:
    """Manage injected AgentLoop and ChannelManager instances on one bus.

    Application entry points own provider/configuration construction. Importing
    this module creates no provider, channel connection, or workspace files.
    """

    def __init__(
        self,
        *,
        agent: AgentRuntime | None = None,
        channels: ChannelRuntime | None = None,
    ) -> None:
        self.agent: AgentRuntime | None = None
        self.channel_manager: ChannelRuntime | None = None
        self.bus: MessageBus | None = None
        self._running_tasks: list[asyncio.Task[None]] = []
        self._started = False
        if agent is not None or channels is not None:
            if agent is None or channels is None:
                raise ValueError("Configure both agent and channels")
            self.configure(agent, channels)

    def configure(self, agent: AgentRuntime, channels: ChannelRuntime) -> None:
        """Attach existing runtimes while stopped, enforcing a shared bus."""
        if self._started:
            raise RuntimeError("Cannot reconfigure a running orchestrator")
        if agent.bus is not channels.bus:
            raise ValueError("Agent and channels must use the same message bus")
        self.agent = agent
        self.channel_manager = channels
        self.bus = agent.bus

    async def start(self) -> None:
        """Start both runtimes in background tasks; repeated calls are harmless."""
        if self._started:
            return
        if self.agent is None or self.channel_manager is None:
            raise RuntimeError("Call configure(agent, channels) before starting")
        self._started = True
        self._running_tasks = [
            asyncio.create_task(self.agent.run(), name="orchestrator.agent"),
            asyncio.create_task(
                self.channel_manager.start_all(), name="orchestrator.channels"
            ),
        ]
        try:
            # Surface immediate startup errors rather than leaving failed tasks
            # behind an apparently successful start.
            await asyncio.sleep(0)
            self._check_tasks()
        except BaseException:
            await self.stop()
            raise
        logger.info("Orchestrator started")

    def _check_tasks(self) -> None:
        for task in self._running_tasks:
            if task.done() and not task.cancelled():
                error = task.exception()
                if error is not None:
                    raise error

    async def stop(self) -> None:
        """Stop and await owned tasks, including after failed startup."""
        if not self._started:
            return
        self._started = False
        try:
            if self.channel_manager is not None:
                await self.channel_manager.stop_all()
        finally:
            try:
                if self.agent is not None:
                    self.agent.stop()
            finally:
                tasks, self._running_tasks = self._running_tasks, []
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                if self.agent is not None:
                    await self.agent.close_mcp()
        logger.info("Orchestrator stopped")

    async def handle_inbound_message(self, message: Message | InboundMessage) -> None:
        """Enqueue a message from trusted application code with explicit routing.

        Channel ingress must still enforce its own sender authorization. Legacy
        Message callers must supply channel_name, user_id and chat_id/channel_id;
        missing identifiers are rejected rather than merging unknown sessions.
        """
        if not self._started or self.bus is None or self.channel_manager is None:
            raise RuntimeError("Orchestrator is not running")
        self._check_tasks()
        if isinstance(message, Message):
            if message.role != MessageRole.USER:
                raise ValueError("Only user messages may enter the inbound queue")
            metadata = message.metadata
            channel = self._route_value(metadata.get("channel_name"))
            chat_key = "channel_id" if channel == "discord" else "chat_id"
            message = InboundMessage(
                channel=channel,
                sender_id=self._route_value(metadata.get("user_id")),
                chat_id=self._route_value(metadata.get(chat_key)),
                content=message.content or "",
                timestamp=message.timestamp,
                metadata=dict(metadata),
            )
        if message.channel not in self.channel_manager.enabled_channels:
            raise ValueError("Message channel is not configured")
        await self.bus.publish_inbound(message)

    @staticmethod
    def _route_value(value: object) -> str:
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise ValueError("Message requires explicit channel, sender and recipient")
        result = str(value).strip()
        if not result:
            raise ValueError("Message routing identifiers must not be empty")
        return result


# Backward-compatible import surface; applications must configure before start.
orchestrator = Orchestrator()
