"""Tests for /stop task cancellation."""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import gettempdir
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_loop():
    """Create a minimal AgentLoop with mocked dependencies."""
    from amberclaw.agent.loop import (  # noqa: PLC0415 - import after dependency fixtures are installed
        AgentLoop,
    )
    from amberclaw.bus.queue import (  # noqa: PLC0415 - import after dependency fixtures are installed
        MessageBus,
    )

    bus = MessageBus()
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    workspace = Path(gettempdir()) / "amberclaw_test_task_cancel"
    workspace.mkdir(parents=True, exist_ok=True)

    with (
        patch("amberclaw.agent.loop.ContextBuilder"),
        patch("amberclaw.agent.loop.SessionManager"),
        patch("amberclaw.agent.loop.SubagentManager") as mock_subagent_manager,
    ):
        mock_subagent_manager.return_value.cancel_by_session = AsyncMock(return_value=0)
        loop = AgentLoop(bus=bus, provider=provider, workspace=workspace)
    return loop, bus


class TestHandleStop:
    @pytest.mark.asyncio
    async def test_stop_no_active_task(self):
        from amberclaw.bus.events import (  # noqa: PLC0415 - import after dependency fixtures are installed
            InboundMessage,
        )

        loop, bus = _make_loop()
        msg = InboundMessage(
            channel="test", sender_id="u1", chat_id="c1", content="/stop"
        )
        await loop._handle_stop(msg)
        out = await asyncio.wait_for(bus.consume_outbound(), timeout=1.0)
        assert "No active task" in out.content

    @pytest.mark.asyncio
    async def test_stop_cancels_active_task(self):
        from amberclaw.bus.events import (  # noqa: PLC0415 - import after dependency fixtures are installed
            InboundMessage,
        )

        loop, bus = _make_loop()
        cancelled = asyncio.Event()

        async def slow_task():
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                cancelled.set()
                raise

        task = asyncio.create_task(slow_task())
        await asyncio.sleep(0)
        loop._active_tasks["test:c1"] = [task]

        msg = InboundMessage(
            channel="test", sender_id="u1", chat_id="c1", content="/stop"
        )
        await loop._handle_stop(msg)

        assert cancelled.is_set()
        out = await asyncio.wait_for(bus.consume_outbound(), timeout=1.0)
        assert "stopped" in out.content.lower()

    @pytest.mark.asyncio
    async def test_stop_cancels_multiple_tasks(self):
        from amberclaw.bus.events import (  # noqa: PLC0415 - import after dependency fixtures are installed
            InboundMessage,
        )

        loop, bus = _make_loop()
        events = [asyncio.Event(), asyncio.Event()]

        async def slow(idx):
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                events[idx].set()
                raise

        tasks = [asyncio.create_task(slow(i)) for i in range(2)]
        await asyncio.sleep(0)
        loop._active_tasks["test:c1"] = tasks

        msg = InboundMessage(
            channel="test", sender_id="u1", chat_id="c1", content="/stop"
        )
        await loop._handle_stop(msg)

        assert all(e.is_set() for e in events)
        out = await asyncio.wait_for(bus.consume_outbound(), timeout=1.0)
        assert "2 task" in out.content


class TestDispatch:
    @pytest.mark.asyncio
    async def test_dispatch_processes_and_publishes(self):
        from amberclaw.bus.events import (  # noqa: PLC0415 - import after dependency fixtures are installed
            InboundMessage,
            OutboundMessage,
        )

        loop, bus = _make_loop()
        msg = InboundMessage(
            channel="test", sender_id="u1", chat_id="c1", content="hello"
        )
        loop._process_message = AsyncMock(
            return_value=OutboundMessage(channel="test", chat_id="c1", content="hi"),
        )
        await loop._dispatch(msg)
        out = await asyncio.wait_for(bus.consume_outbound(), timeout=1.0)
        assert out.content == "hi"

    @pytest.mark.asyncio
    async def test_processing_lock_serializes(self):
        from amberclaw.bus.events import (  # noqa: PLC0415 - import after dependency fixtures are installed
            InboundMessage,
            OutboundMessage,
        )

        loop, _bus = _make_loop()
        order = []

        async def mock_process(m, **_kwargs):
            order.append(f"start-{m.content}")
            await asyncio.sleep(0.05)
            order.append(f"end-{m.content}")
            return OutboundMessage(channel="test", chat_id="c1", content=m.content)

        loop._process_message = mock_process
        msg1 = InboundMessage(channel="test", sender_id="u1", chat_id="c1", content="a")
        msg2 = InboundMessage(channel="test", sender_id="u1", chat_id="c1", content="b")

        t1 = asyncio.create_task(loop._dispatch(msg1))
        t2 = asyncio.create_task(loop._dispatch(msg2))
        await asyncio.gather(t1, t2)
        assert order == ["start-a", "end-a", "start-b", "end-b"]


class TestSubagentCancellation:
    @pytest.mark.asyncio
    async def test_cancel_by_session(self):
        from amberclaw.agent.subagent import (  # noqa: PLC0415 - import after dependency fixtures are installed
            SubagentManager,
        )
        from amberclaw.bus.queue import (  # noqa: PLC0415 - import after dependency fixtures are installed
            MessageBus,
        )

        bus = MessageBus()
        provider = MagicMock()
        provider.get_default_model.return_value = "test-model"
        mgr = SubagentManager(provider=provider, workspace=MagicMock(), bus=bus)

        cancelled = asyncio.Event()

        async def slow():
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                cancelled.set()
                raise

        task = asyncio.create_task(slow())
        await asyncio.sleep(0)
        mgr._running_tasks["sub-1"] = task
        mgr._session_tasks["test:c1"] = {"sub-1"}

        count = await mgr.cancel_by_session("test:c1")
        assert count == 1
        assert cancelled.is_set()

    @pytest.mark.asyncio
    async def test_cancel_by_session_no_tasks(self):
        from amberclaw.agent.subagent import (  # noqa: PLC0415 - import after dependency fixtures are installed
            SubagentManager,
        )
        from amberclaw.bus.queue import (  # noqa: PLC0415 - import after dependency fixtures are installed
            MessageBus,
        )

        bus = MessageBus()
        provider = MagicMock()
        provider.get_default_model.return_value = "test-model"
        mgr = SubagentManager(provider=provider, workspace=MagicMock(), bus=bus)
        assert await mgr.cancel_by_session("nonexistent") == 0
