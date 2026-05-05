import asyncio
import signal
import sys
import typer
from typing import Any, Iterator
from rich.console import Console
from contextlib import contextmanager

from amberclaw import __logo__
from amberclaw.cli.commands import utils
from amberclaw.config import loader, paths
from amberclaw.providers import factory
from amberclaw.utils import helpers

console = Console()

def agent(
    message: str = typer.Option(None, "--message", "-m", help="Message to send to the agent"),
    session_id: str = typer.Option("cli:direct", "--session", "-s", help="Session ID"),
    workspace: str | None = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
    markdown: bool = typer.Option(
        True, "--markdown/--no-markdown", help="Render assistant output as Markdown"
    ),
    logs: bool = typer.Option(
        False, "--logs/--no-logs", help="Show amberclaw runtime logs during chat"
    ),
) -> None:
    """Interact with the agent directly."""
    from loguru import logger
    from amberclaw.agent.loop import AgentLoop
    from amberclaw.bus.queue import MessageBus
    from amberclaw.cron.service import CronService

    try:
        cfg = loader.load_runtime_config(config, workspace)
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
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

    @contextmanager
    def _thinking_ctx() -> Iterator[Any]:
        if logs:
            yield None
            return
        status = console.status("[dim]AmberClaw is thinking...[/dim]", spinner="dots")
        status.start()
        try:
            yield status
        finally:
            status.stop()

    async def _cli_progress(content: str, *, tool_hint: bool = False) -> None:
        ch = agent_loop.channels_config
        if ch and tool_hint and not ch.send_tool_hints:
            return
        if ch and not tool_hint and not ch.send_progress:
            return
        console.print(f"  [dim]↳ {content}[/dim]")

    if message:
        async def run_once() -> None:
            streamer = utils.TokenStreamer(console, render_markdown=markdown)
            with _thinking_ctx():
                response = await agent_loop.process_direct(
                    message, session_id, on_progress=_cli_progress, on_token=streamer.on_token
                )
            streamer.stop()
            if not streamer.content:
                utils._print_agent_response(response, render_markdown=markdown)
            await agent_loop.close_mcp()

        asyncio.run(run_once())
    else:
        from amberclaw.bus.events import InboundMessage
        utils._init_prompt_session()
        console.print(
            f"{__logo__} Interactive mode (type [bold]exit[/bold] or [bold]Ctrl+C[/bold] to quit)\n"
        )

        if ":" in session_id:
            cli_channel, cli_chat_id = session_id.split(":", 1)
        else:
            cli_channel, cli_chat_id = "cli", session_id

        def _handle_signal(signum: int, frame: Any) -> None:
            sig_name = signal.Signals(signum).name
            utils._restore_terminal()
            console.print(f"\nReceived {sig_name}, goodbye!")
            sys.exit(0)

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)
        if hasattr(signal, "SIGHUP"):
            signal.signal(signal.SIGHUP, _handle_signal)
        if hasattr(signal, "SIGPIPE"):
            signal.signal(signal.SIGPIPE, signal.SIG_IGN)

        async def run_interactive() -> None:
            bus_task = asyncio.create_task(agent_loop.run())
            turn_done = asyncio.Event()
            turn_done.set()
            turn_response: list[str] = []

            state = {
                "active_status": None,
                "streamer": utils.TokenStreamer(console, render_markdown=markdown),
            }

            async def _consume_outbound() -> None:
                while True:
                    try:
                        msg = await asyncio.wait_for(bus.consume_outbound(), timeout=1.0)
                        if msg.metadata.get("_token"):
                            if state["active_status"]:
                                state["active_status"].stop()
                                state["active_status"] = None
                            await state["streamer"].on_token(msg.content)
                            continue

                        if msg.metadata.get("_progress"):
                            is_tool_hint = msg.metadata.get("_tool_hint", False)
                            ch = agent_loop.channels_config
                            if (ch and is_tool_hint and not ch.send_tool_hints) or (
                                ch and not is_tool_hint and not ch.send_progress
                            ):
                                pass
                            else:
                                console.print(f"  [dim]↳ {msg.content}[/dim]")
                        elif not turn_done.is_set():
                            if state["streamer"].header_printed:
                                state["streamer"].stop()
                                state["streamer"] = utils.TokenStreamer(console, render_markdown=markdown)
                            elif msg.content:
                                turn_response.append(msg.content)
                            turn_done.set()
                        elif msg.content:
                            console.print()
                            utils._print_agent_response(msg.content, render_markdown=markdown)
                    except asyncio.TimeoutError:
                        continue
                    except asyncio.CancelledError:
                        break

            outbound_task = asyncio.create_task(_consume_outbound())

            try:
                while True:
                    try:
                        utils._flush_pending_tty_input()
                        user_input = await utils._read_interactive_input_async()
                        command = user_input.strip()
                        if not command:
                            continue

                        if utils._is_exit_command(command):
                            utils._restore_terminal()
                            console.print("\nGoodbye!")
                            break

                        turn_done.clear()
                        turn_response.clear()

                        await bus.publish_inbound(
                            InboundMessage(
                                channel=cli_channel,
                                sender_id="user",
                                chat_id=cli_chat_id,
                                content=user_input,
                            )
                        )

                        with _thinking_ctx() as status:
                            state["active_status"] = status
                            await turn_done.wait()

                        if turn_response:
                            utils._print_agent_response(turn_response[0], render_markdown=markdown)
                    except KeyboardInterrupt:
                        utils._restore_terminal()
                        console.print("\nGoodbye!")
                        break
                    except EOFError:
                        utils._restore_terminal()
                        console.print("\nGoodbye!")
                        break
            finally:
                agent_loop.stop()
                outbound_task.cancel()
                await asyncio.gather(bus_task, outbound_task, return_exceptions=True)
                await agent_loop.close_mcp()

        asyncio.run(run_interactive())
