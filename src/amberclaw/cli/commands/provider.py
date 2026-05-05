import typer
from rich.console import Console
from amberclaw.providers import registry

provider_app = typer.Typer(help="Manage AI providers and API keys.")
console = Console()

@provider_app.command()
def list():
    """List supported AI providers."""
    console.print("[bold cyan]Supported AI Providers:[/bold cyan]\n")
    for spec in registry.PROVIDERS:
        type_str = " (OAuth)" if spec.is_oauth else ""
        console.print(f" • {spec.label}{type_str}")

@provider_app.command()
def login(name: str):
    """Login to a provider (for OAuth based providers like Codex)."""
    from amberclaw.providers import openai_codex_provider
    
    if name.lower() == "codex":
        console.print("[cyan]Initiating Codex OAuth login...[/cyan]")
        openai_codex_provider.login()
    else:
        console.print(f"[red]Provider '{name}' does not support OAuth login.[/red]")
