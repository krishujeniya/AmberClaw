"""CLI runtime characterization and deterministic cleanup regressions."""

import asyncio
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from amberclaw.bus.events import OutboundMessage
from amberclaw.bus.queue import MessageBus
from amberclaw.cli.commands import app
from amberclaw.config.schema import Config

runner = CliRunner()


@pytest.fixture
def runtime(tmp_path: Path) -> Iterator[SimpleNamespace]:
    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path)
    loop = MagicMock()
    loop.channels_config = cfg.channels
    loop.model = "offline-model"
    loop.process_direct = AsyncMock(return_value="offline response")
    loop.close_mcp = AsyncMock()
    loop.run = AsyncMock()
    bus = MessageBus()
    cron = MagicMock()
    cron.start = AsyncMock()
    cron.status.return_value = {"jobs": 0}
    heartbeat = MagicMock()
    heartbeat.start = AsyncMock()
    heartbeat.stop = AsyncMock()
    channels = MagicMock()
    channels.enabled_channels = ["slack"]
    channels.start_all = AsyncMock()
    channels.stop_all = AsyncMock()
    sessions = MagicMock()
    sessions.list_sessions.return_value = [
        {"key": "cli:direct"},
        {"key": "discord:ignored"},
        {"key": "slack:group:topic"},
    ]
    with (
        patch("amberclaw.config.loader.load_runtime_config", return_value=cfg),
        patch("amberclaw.providers.factory.make_provider", return_value=object()),
        patch("amberclaw.utils.helpers.sync_workspace_templates"),
        patch("amberclaw.config.paths.get_cron_dir", return_value=tmp_path),
        patch("amberclaw.bus.queue.MessageBus", return_value=bus),
        patch("amberclaw.agent.loop.AgentLoop", return_value=loop),
        patch("amberclaw.cron.service.CronService", return_value=cron),
        patch(
            "amberclaw.cron.HeartbeatService", return_value=heartbeat
        ) as heartbeat_cls,
        patch("amberclaw.channels.manager.ChannelManager", return_value=channels),
        patch("amberclaw.session.manager.SessionManager", return_value=sessions),
        patch("amberclaw.cli.commands.utils._print_agent_response") as output,
    ):
        yield SimpleNamespace(
            loop=loop,
            bus=bus,
            cron=cron,
            heartbeat=heartbeat,
            heartbeat_cls=heartbeat_cls,
            channels=channels,
            output=output,
        )


def test_one_shot_callbacks_preserve_progress_filters(runtime: SimpleNamespace) -> None:
    async def respond(*_args: object, **kwargs: object) -> str:
        progress = kwargs["on_progress"]
        assert callable(progress)
        await progress("visible progress")
        await progress("hidden tool", tool_hint=True)
        return "offline response"

    runtime.loop.channels_config.send_progress = True
    runtime.loop.channels_config.send_tool_hints = False
    runtime.loop.process_direct.side_effect = respond
    result = runner.invoke(app, ["agent", "-m", "hello", "-s", "cli:custom", "--logs"])
    assert result.exit_code == 0, result.exception
    assert "visible progress" in result.output
    assert "hidden tool" not in result.output
    assert runtime.loop.process_direct.await_args.args == ("hello", "cli:custom")
    runtime.output.assert_called_once_with("offline response", render_markdown=True)


def test_interactive_stream_and_session_routing(runtime: SimpleNamespace) -> None:
    stopped = asyncio.Event()
    streamer = MagicMock()
    streamer.header_printed = False

    async def token(_content: str) -> None:
        streamer.header_printed = True

    streamer.on_token = AsyncMock(side_effect=token)

    async def run() -> None:
        message = await runtime.bus.consume_inbound()
        assert message.channel == "slack"
        assert message.chat_id == "group:topic"
        assert message.content == "hello"
        for metadata, content in [
            ({"_token": True}, "streamed response"),
            ({"_progress": True}, "progress"),
            ({}, "final response"),
        ]:
            await runtime.bus.publish_outbound(
                OutboundMessage(
                    channel="slack",
                    chat_id="group:topic",
                    content=content,
                    metadata=metadata,
                )
            )
        await stopped.wait()

    runtime.loop.run.side_effect = run
    runtime.loop.stop.side_effect = stopped.set
    with (
        patch("amberclaw.cli.commands.utils._init_prompt_session"),
        patch("amberclaw.cli.commands.utils._flush_pending_tty_input"),
        patch("amberclaw.cli.commands.utils._restore_terminal"),
        patch(
            "amberclaw.cli.commands.utils._read_interactive_input_async",
            AsyncMock(side_effect=["hello", "exit"]),
        ),
        patch("amberclaw.cli.commands.utils.TokenStreamer", return_value=streamer),
        patch("amberclaw.cli.commands.agent.signal.signal"),
    ):
        result = runner.invoke(app, ["agent", "-s", "slack:group:topic"])
    assert result.exit_code == 0, result.exception
    streamer.on_token.assert_awaited_once_with("streamed response")
    assert "progress" in result.output
    runtime.output.assert_not_called()
    runtime.loop.close_mcp.assert_awaited_once()


def test_gateway_callbacks_keep_cron_and_heartbeat_routes(
    runtime: SimpleNamespace,
) -> None:
    async def cron_start() -> None:
        job = SimpleNamespace(
            id="fixture-job",
            name="fixture reminder",
            payload=SimpleNamespace(
                message="do this", channel="slack", to="group", deliver=True
            ),
        )
        await runtime.cron.on_job(job)

    async def heartbeat_start() -> None:
        callbacks = runtime.heartbeat_cls.call_args.kwargs
        assert await callbacks["on_execute"]("check in") == "offline response"
        await callbacks["on_notify"]("notification")

    runtime.cron.start.side_effect = cron_start
    runtime.heartbeat.start.side_effect = heartbeat_start
    runtime.loop.tools.get.return_value = None
    result = runner.invoke(app, ["gateway"])
    assert result.exit_code == 0, result.exception
    cron_call, heartbeat_call = runtime.loop.process_direct.await_args_list
    assert cron_call.kwargs == {
        "session_key": "cron:fixture-job",
        "channel": "slack",
        "chat_id": "group",
    }
    assert "Scheduled instruction: do this" in cron_call.args[0]
    assert heartbeat_call.args == ("check in",)
    assert heartbeat_call.kwargs["session_key"] == "heartbeat"
    assert heartbeat_call.kwargs["chat_id"] == "group:topic"
    outbound = asyncio.run(runtime.bus.consume_outbound())
    assert outbound.content == "offline response"
    outbound = asyncio.run(runtime.bus.consume_outbound())
    assert (outbound.channel, outbound.chat_id, outbound.content) == (
        "slack",
        "group:topic",
        "notification",
    )


@pytest.mark.parametrize(
    "failure",
    [
        "cron",
        "heartbeat",
        "agent",
        "close",
        "stop",
        "cron stop",
        "heartbeat stop",
        "channels stop",
    ],
)
def test_gateway_drains_all_resources_in_order(
    runtime: SimpleNamespace, failure: str
) -> None:
    calls: list[str] = []

    def record(event: str) -> None:
        calls.append(event)
        if failure == event:
            raise RuntimeError(f"offline {event}")

    runtime.loop.stop.side_effect = lambda: record("stop")
    runtime.loop.close_mcp.side_effect = lambda: record("close")
    runtime.cron.stop.side_effect = lambda: record("cron stop")
    runtime.heartbeat.stop.side_effect = lambda: record("heartbeat stop")
    runtime.channels.stop_all.side_effect = lambda: record("channels stop")
    target = {
        "cron": runtime.cron.start,
        "heartbeat": runtime.heartbeat.start,
        "agent": runtime.loop.run,
    }.get(failure)
    if target is not None:
        target.side_effect = RuntimeError(f"offline {failure}")
    result = runner.invoke(app, ["gateway"])
    assert isinstance(result.exception, RuntimeError)
    assert calls.index("stop") < calls.index("close")
    assert {"stop", "close", "cron stop", "heartbeat stop", "channels stop"} <= set(
        calls
    )


def test_one_shot_closes_even_when_streamer_cleanup_fails(
    runtime: SimpleNamespace,
) -> None:
    calls: list[str] = []
    streamer = MagicMock()
    streamer.stop.side_effect = RuntimeError("offline stream cleanup")
    runtime.loop.stop.side_effect = lambda: calls.append("stop")
    runtime.loop.close_mcp.side_effect = lambda: calls.append("close")
    with patch("amberclaw.cli.commands.utils.TokenStreamer", return_value=streamer):
        result = runner.invoke(app, ["agent", "-m", "hello"])
    assert isinstance(result.exception, RuntimeError)
    assert calls == ["stop", "close"]


def test_interactive_start_failure_closes_and_cancels_input(
    runtime: SimpleNamespace,
) -> None:
    calls: list[str] = []
    input_cancelled: list[bool] = []
    runtime.loop.run.side_effect = RuntimeError("offline startup")
    runtime.loop.stop.side_effect = lambda: calls.append("stop")
    runtime.loop.close_mcp.side_effect = lambda: calls.append("close")

    async def read() -> str:
        try:
            await asyncio.wait_for(asyncio.Event().wait(), timeout=0.1)
        finally:
            input_cancelled.append(True)
        return "unreachable"

    with (
        patch("amberclaw.cli.commands.utils._init_prompt_session"),
        patch("amberclaw.cli.commands.utils._flush_pending_tty_input"),
        patch("amberclaw.cli.commands.utils._read_interactive_input_async", read),
        patch("amberclaw.cli.commands.agent.signal.signal"),
    ):
        result = runner.invoke(app, ["agent"])
    assert isinstance(result.exception, RuntimeError)
    assert str(result.exception) == "offline startup"
    assert calls == ["stop", "close"]
    assert input_cancelled == [True]
