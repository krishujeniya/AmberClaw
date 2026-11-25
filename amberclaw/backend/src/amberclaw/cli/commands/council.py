import asyncio

import typer
from rich.console import Console

from amberclaw import __logo__
from amberclaw.cli.commands import utils
from amberclaw.config import loader
from amberclaw.providers import factory

console = Console()


def council(
    topic: str = typer.Argument(..., help="Topic to debate in the council"),
    agents: str = typer.Option(
        "",
        "--models",
        "--agents",
        help="Comma-separated model IDs (--agents is a compatibility alias); defaults to the configured model",
    ),
) -> None:
    """Consult a council of models and synthesize their answers."""
    from amberclaw.agent.tools import (  # noqa: PLC0415 - defer runtime and platform initialization until command use
        council as council_mod,
    )

    cfg = loader.load_runtime_config()
    provider = factory.make_provider(cfg)

    council_tool = council_mod.CouncilTool(
        provider=provider, model=cfg.agents.defaults.model
    )

    async def run_council() -> None:
        console.print(
            f"{__logo__} [bold yellow]Summoning the Council...[/bold yellow]\n"
        )

        args = council_mod.CouncilArgs(
            query=topic,
            models=[model.strip() for model in agents.split(",") if model.strip()],
        )
        response = await council_tool.run(args)

        utils._print_agent_response(response, render_markdown=True)

    asyncio.run(run_council())
