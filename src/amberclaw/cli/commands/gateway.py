from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import TYPE_CHECKING

import typer
from rich.console import Console

from amberclaw import __logo__
from amberclaw.config import loader, paths
from amberclaw.providers import factory
from amberclaw.utils import helpers

if TYPE_CHECKING:
    from amberclaw.agent.loop import AgentLoop
    from amberclaw.bus.queue import MessageBus
    from amberclaw.channels.manager import ChannelManager
    from amberclaw.cron.heartbeat import HeartbeatService
    from amberclaw.cron.service import CronService
    from amberclaw.cron.types import CronJob
    from amberclaw.session.manager import SessionManager

console = Console()


def gateway(
    port: int | None = typer.Option(None, "--port", "-p", help="Gateway port"),
    workspace: str | None = typer.Option(
        None, "--workspace", "-w", help="Workspace directory"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    config: str | None = typer.Option(
        None, "--config", "-c", help="Path to config file"
    ),
) -> None:
    """Start the AmberClaw gateway."""
    from amberclaw.agent.loop import (  # noqa: PLC0415 - defer runtime and platform initialization until command use
        AgentLoop,
    )
    from amberclaw.bus.queue import (  # noqa: PLC0415 - defer runtime and platform initialization until command use
        MessageBus,
    )
    from amberclaw.channels.manager import (  # noqa: PLC0415 - defer runtime and platform initialization until command use
        ChannelManager,
    )
    from amberclaw.cron import (  # noqa: PLC0415 - defer runtime and platform initialization until command use
        HeartbeatService,
    )
    from amberclaw.cron.service import (  # noqa: PLC0415 - defer runtime and platform initialization until command use
        CronService,
    )
    from amberclaw.session.manager import (  # noqa: PLC0415 - defer runtime and platform initialization until command use
        SessionManager,
    )

    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    try:
        cfg = loader.load_runtime_config(config, workspace)
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e
    port_num = port if port is not None else cfg.gateway.port

    console.print(f"{__logo__} Starting AmberClaw gateway on port {port_num}...")
    helpers.sync_workspace_templates(cfg.workspace_path)
    bus = MessageBus()
    provider = factory.make_provider(cfg)
    session_manager = SessionManager(cfg.workspace_path)

    cron_store_path = paths.get_cron_dir() / "jobs.json"
    cron = CronService(cron_store_path)

    agent = AgentLoop(
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
        session_manager=session_manager,
        mcp_servers=cfg.tools.mcp_servers,
        channels_config=cfg.channels,
        embedding_model=cfg.agents.defaults.embedding_model,
        reranker_model=cfg.agents.defaults.reranker_model,
    )

    channels = ChannelManager(cfg, bus)
    callbacks = _GatewayCallbacks(agent, bus, channels, session_manager)
    cron.on_job = callbacks.on_cron_job

    hb_cfg = cfg.gateway.heartbeat
    heartbeat = HeartbeatService(
        workspace=cfg.workspace_path,
        provider=provider,
        model=agent.model,
        on_execute=callbacks.on_heartbeat_execute,
        on_notify=callbacks.on_heartbeat_notify,
        interval_s=hb_cfg.interval_s,
        enabled=hb_cfg.enabled,
    )

    if channels.enabled_channels:
        console.print(
            f"[green]✓[/green] Channels enabled: {', '.join(channels.enabled_channels)}"
        )
    else:
        console.print("[yellow]Warning: No channels enabled[/yellow]")

    cron_status = cron.status()
    if cron_status["jobs"] > 0:
        console.print(f"[green]✓[/green] Cron: {cron_status['jobs']} scheduled jobs")

    console.print(f"[green]✓[/green] Heartbeat: every {hb_cfg.interval_s}s")

    asyncio.run(_run_gateway(agent, channels, cron, heartbeat))


@dataclass
class _GatewayCallbacks:
    agent: AgentLoop
    bus: MessageBus
    channels: ChannelManager
    session_manager: SessionManager

    async def on_cron_job(self, job: CronJob) -> str | None:
        from amberclaw.agent.tools.cron import (  # noqa: PLC0415 - defer runtime and platform initialization until command use
            CronTool,
        )
        from amberclaw.agent.tools.message import (  # noqa: PLC0415 - defer runtime and platform initialization until command use
            MessageTool,
        )

        reminder_note = (
            "[Scheduled Task] Timer finished.\n\n"
            f"Task '{job.name}' has been triggered.\n"
            f"Scheduled instruction: {job.payload.message}"
        )

        cron_tool = self.agent.tools.get("cron")
        cron_token = None
        if isinstance(cron_tool, CronTool):
            cron_token = cron_tool.set_cron_context(True)
        try:
            response = await self.agent.process_direct(
                reminder_note,
                session_key=f"cron:{job.id}",
                channel=job.payload.channel or "cli",
                chat_id=job.payload.to or "direct",
            )
        finally:
            if isinstance(cron_tool, CronTool) and cron_token is not None:
                cron_tool.reset_cron_context(cron_token)

        message_tool = self.agent.tools.get("message")
        if isinstance(message_tool, MessageTool) and message_tool._sent_in_turn:
            return response

        if job.payload.deliver and job.payload.to and response:
            from amberclaw.bus.events import (  # noqa: PLC0415 - defer runtime and platform initialization until command use
                OutboundMessage,
            )

            await self.bus.publish_outbound(
                OutboundMessage(
                    channel=job.payload.channel or "cli",
                    chat_id=job.payload.to,
                    content=response,
                )
            )
        return response

    def _pick_heartbeat_target(self) -> tuple[str, str]:
        enabled = set(self.channels.enabled_channels)
        for item in self.session_manager.list_sessions():
            key = item.get("key") or ""
            if ":" not in key:
                continue
            channel, chat_id = key.split(":", 1)
            if channel in {"cli", "system"}:
                continue
            if channel in enabled and chat_id:
                return channel, chat_id
        return "cli", "direct"

    async def on_heartbeat_execute(self, tasks: str) -> str:
        channel, chat_id = self._pick_heartbeat_target()

        async def _silent(*_args: object, **_kwargs: object) -> None:
            pass

        return await self.agent.process_direct(
            tasks,
            session_key="heartbeat",
            channel=channel,
            chat_id=chat_id,
            on_progress=_silent,
        )

    async def on_heartbeat_notify(self, response: str) -> None:
        from amberclaw.bus.events import (  # noqa: PLC0415 - defer runtime and platform initialization until command use
            OutboundMessage,
        )

        channel, chat_id = self._pick_heartbeat_target()
        if channel == "cli":
            return
        await self.bus.publish_outbound(
            OutboundMessage(channel=channel, chat_id=chat_id, content=response)
        )


async def _run_gateway(
    agent: AgentLoop,
    channels: ChannelManager,
    cron: CronService,
    heartbeat: HeartbeatService,
) -> None:
    tasks: list[asyncio.Task[None]] = []

    async def cancel_tasks() -> None:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async with AsyncExitStack() as cleanup:
        # Reverse registration order stops work before draining tool transports.
        # ExitStack attempts every cleanup even when an earlier cleanup fails.
        cleanup.push_async_callback(channels.stop_all)
        cleanup.push_async_callback(agent.close_mcp)
        cleanup.push_async_callback(cancel_tasks)
        cleanup.push_async_callback(heartbeat.stop)
        cleanup.callback(cron.stop)
        cleanup.callback(agent.stop)
        try:
            await cron.start()
            await heartbeat.start()
            tasks.append(asyncio.create_task(agent.run()))
            tasks.append(asyncio.create_task(channels.start_all()))
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            console.print("\nShutting down...")
