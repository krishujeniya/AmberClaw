import asyncio

import typer
from rich.console import Console

from amberclaw import __logo__
from amberclaw.cli.commands import utils
from amberclaw.config import loader
from amberclaw.providers import factory

console = Console()


def mythos(
    query: str = typer.Argument(..., help="Query to explore the world mythos"),
) -> None:
    """Explore the collective knowledge and lore (Mythos)."""
    from amberclaw.agent.tools import (  # noqa: PLC0415 - defer runtime and platform initialization until command use
        mythos as mythos_mod,
    )

    cfg = loader.load_runtime_config()
    provider = factory.make_provider(cfg)

    mythos_tool = mythos_mod.MythosTool(
        provider=provider, model=cfg.agents.defaults.model
    )

    async def run_mythos() -> None:
        console.print(
            f"{__logo__} [bold magenta]Consulting the Mythos...[/bold magenta]\n"
        )

        args = mythos_mod.MythosArgs(query=query)
        response = await mythos_tool.run(args)

        utils._print_agent_response(response, render_markdown=True)

    asyncio.run(run_mythos())
