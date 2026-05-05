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
    agents: str = typer.Option("strategist,expert,critic", "--agents", help="Comma-separated agent keys"),
) -> None:
    """Summon a council of expert agents to debate a topic."""
    from amberclaw.agent.tools import council as council_mod

    cfg = loader.load_runtime_config()
    provider = factory.make_provider(cfg)
    
    council_tool = council_mod.CouncilTool(
        provider=provider,
        workspace=cfg.workspace_path,
        model=cfg.agents.defaults.model
    )
    
    async def run_council():
        streamer = utils.TokenStreamer(console)
        console.print(f"{__logo__} [bold yellow]Summoning the Council...[/bold yellow]\n")
        
        args = council_mod.CouncilArgs(topic=topic, agents=agents.split(","))
        response = await council_tool._run(args)
        
        utils._print_agent_response(response)
        
    asyncio.run(run_council())
