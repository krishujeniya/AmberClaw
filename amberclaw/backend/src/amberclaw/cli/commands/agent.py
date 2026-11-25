from __future__ import annotations

import asyncio
import signal
import sys
from collections.abc import Iterator
from contextlib import AsyncExitStack, contextmanager
from dataclasses import dataclass, field
from types import FrameType
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.status import Status

from amberclaw import __logo__
from amberclaw.cli.commands import utils
from amberclaw.config import loader, paths
from amberclaw.providers import factory
from amberclaw.utils import helpers

if TYPE_CHECKING:
    from amberclaw.agent.loop import AgentLoop
    from amberclaw.bus.events import OutboundMessage
    from amberclaw.bus.queue import MessageBus

console = Console()


def agent(  # noqa: PLR0913 - preserve public positional CLI options
    message: str = typer.Option(
        None, "--message", "-m", help="Message to send to the agent"
    ),
    session_id: str = typer.Option("cli:direct", "--session", "-s", help="Session ID"),
    workspace: str | None = typer.Option(
        None, "--workspace", "-w", help="Workspace directory"
    ),
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
    markdown: bool = typer.Option(
        True, "--markdown/--no-markdown", help="Render assistant output as Markdown"
    ),
    logs: bool = typer.Option(
        False, "--logs/--no-logs", help="Show amberclaw runtime logs during chat"
    ),
) -> None:
    """Interact with the agent directly."""
    from loguru import (  # noqa: PLC0415 - defer runtime and platform initialization until command use
        logger,
    )

    from amberclaw.agent.loop import (  # noqa: PLC0415 - defer runtime and platform initialization until command use
        AgentLoop,
    )
    from amberclaw.bus.queue import (  # noqa: PLC0415 - defer runtime and platform initialization until command use
        MessageBus,
    )
    from amberclaw.cron.service import (  # noqa: PLC0415 - defer runtime and platform initialization until command use
        CronService,
    )

    try:
        cfg = loader.load_runtime_config(config, workspace)
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e
    helpers.sync_workspace_templates(cfg.workspace_path)

    bus = MessageBus()
    provider = factory.make_provider(cfg)

    cron_store_path = paths.get_cron_dir() / "jobs.json"
    cron = CronService(cron_store_path)

    if logs:
        logger.enable("amberclaw")
    else:
        logger.disable("amberclaw")

    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=cfg.workspace_path,
        model=cfg.agents.defaults.model,
        temperature=cfg.agents.defaults.temperature,
        max_tokens=cfg.agents.defaults.max_tokens,
        max_iterations=cfg.agents.defaults.max_tool_iterations,
        memory_window=cfg.agents.defaults.memory_window,
        reasoning_effort=cfg.agents.defaults.reasoning_effort,
        brave_api_key=cfg.tools.web.search.api_key or None,
        web_proxy=cfg.tools.web.proxy or None,
        exec_config=cfg.tools.exec,
        cron_service=cron,
        restrict_to_workspace=cfg.tools.restrict_to_workspace,
        mcp_servers=cfg.tools.mcp_servers,
        channels_config=cfg.channels,
        fallback_models=cfg.agents.defaults.fallback_models,
        embedding_model=cfg.agents.defaults.embedding_model,
        reranker_model=cfg.agents.defaults.reranker_model,
    )

    runtime = _AgentCLI(agent_loop, bus, markdown, logs)
    if message:
        asyncio.run(runtime.run_once(message, session_id))
    else:
        _prepare_interactive()
        asyncio.run(runtime.run_interactive(session_id))


@dataclass
class _InteractiveState:
    streamer: utils.TokenStreamer
    active_status: Status | None = None
    turn_done: asyncio.Event = field(default_factory=asyncio.Event)
    turn_response: list[str] = field(default_factory=list)

    def stop_streamer(self) -> None:
        self.streamer.stop()


async def _cancel_tasks(*tasks: asyncio.Task[None]) -> None:
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


def _prepare_interactive() -> None:
    utils._init_prompt_session()
    console.print(
        f"{__logo__} Interactive mode (type [bold]exit[/bold] or [bold]Ctrl+C[/bold] to quit)\n"
    )

    def handle_signal(signum: int, _frame: FrameType | None) -> None:
        sig_name = signal.Signals(signum).name
        utils._restore_terminal()
        console.print(f"\nReceived {sig_name}, goodbye!")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, handle_signal)
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_IGN)


@dataclass
class _AgentCLI:
    agent_loop: AgentLoop
    bus: MessageBus
    markdown: bool
    logs: bool

    @contextmanager
    def thinking(self) -> Iterator[Status | None]:
        if self.logs:
            yield None
            return
        status = console.status("[dim]AmberClaw is thinking...[/dim]", spinner="dots")
        status.start()
        try:
            yield status
        finally:
            status.stop()

    async def progress(self, content: str, *, tool_hint: bool = False) -> None:
        channels = self.agent_loop.channels_config
        if channels and tool_hint and not channels.send_tool_hints:
            return
        if channels and not tool_hint and not channels.send_progress:
            return
        console.print(f"  [dim]↳ {content}[/dim]")

    async def run_once(self, message: str, session_id: str) -> None:
        async with AsyncExitStack() as cleanup:
            cleanup.push_async_callback(self.agent_loop.close_mcp)
            cleanup.callback(self.agent_loop.stop)
            streamer = utils.TokenStreamer(console, render_markdown=self.markdown)
            try:
                with self.thinking():
                    response = await self.agent_loop.process_direct(
                        message,
                        session_id,
                        on_progress=self.progress,
                        on_token=streamer.on_token,
                    )
            finally:
                streamer.stop()
            if not streamer.content:
                utils._print_agent_response(response, render_markdown=self.markdown)

    async def run_interactive(self, session_id: str) -> None:
        state = _InteractiveState(
            streamer=utils.TokenStreamer(console, render_markdown=self.markdown)
        )
        state.turn_done.set()
        async with AsyncExitStack() as cleanup:
            cleanup.push_async_callback(self.agent_loop.close_mcp)
            cleanup.callback(state.stop_streamer)
            bus_task = asyncio.create_task(self.agent_loop.run())
            outbound_task = asyncio.create_task(self.consume_outbound(state))
            input_task = asyncio.create_task(self.read_interactive(session_id, state))
            cleanup.push_async_callback(
                _cancel_tasks, bus_task, outbound_task, input_task
            )
            cleanup.callback(self.agent_loop.stop)
            done, _ = await asyncio.wait(
                (bus_task, outbound_task, input_task),
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in (bus_task, outbound_task, input_task):
                if task in done:
                    await task

    async def consume_outbound(self, state: _InteractiveState) -> None:
        while True:
            try:
                message = await asyncio.wait_for(
                    self.bus.consume_outbound(), timeout=1.0
                )
                await self.handle_outbound(message, state)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    async def handle_outbound(
        self, message: OutboundMessage, state: _InteractiveState
    ) -> None:
        if message.metadata.get("_token"):
            if state.active_status:
                state.active_status.stop()
                state.active_status = None
            await state.streamer.on_token(message.content)
        elif message.metadata.get("_progress"):
            await self.progress(
                message.content, tool_hint=message.metadata.get("_tool_hint", False)
            )
        elif not state.turn_done.is_set():
            if state.streamer.header_printed:
                state.streamer.stop()
                state.streamer = utils.TokenStreamer(
                    console, render_markdown=self.markdown
                )
            elif message.content:
                state.turn_response.append(message.content)
            state.turn_done.set()
        elif message.content:
            console.print()
            utils._print_agent_response(message.content, render_markdown=self.markdown)

    async def read_interactive(self, session_id: str, state: _InteractiveState) -> None:
        from amberclaw.bus.events import (  # noqa: PLC0415 - only interactive mode constructs inbound messages
            InboundMessage,
        )

        channel, chat_id = (
            session_id.split(":", 1) if ":" in session_id else ("cli", session_id)
        )
        while True:
            try:
                utils._flush_pending_tty_input()
                user_input = await utils._read_interactive_input_async()
                command = user_input.strip()
                if not command:
                    continue
                if utils._is_exit_command(command):
                    break
                state.turn_done.clear()
                state.turn_response.clear()
                await self.bus.publish_inbound(
                    InboundMessage(
                        channel=channel,
                        sender_id="user",
                        chat_id=chat_id,
                        content=user_input,
                    )
                )
                with self.thinking() as status:
                    state.active_status = status
                    await state.turn_done.wait()
                if state.turn_response:
                    utils._print_agent_response(
                        state.turn_response[0], render_markdown=self.markdown
                    )
            except (KeyboardInterrupt, EOFError):
                break
        utils._restore_terminal()
        console.print("\nGoodbye!")
