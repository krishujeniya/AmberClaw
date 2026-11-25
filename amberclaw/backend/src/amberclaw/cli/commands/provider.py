import typer
from rich.console import Console

from amberclaw.providers import registry

provider_app = typer.Typer(help="Manage AI providers and API keys.")
console = Console()


@provider_app.command("list")
def list_providers() -> None:
    """List supported AI providers."""
    console.print("[bold cyan]Supported AI Providers:[/bold cyan]\n")
    for spec in registry.PROVIDERS:
        type_str = " (OAuth)" if spec.is_oauth else ""
        console.print(f" • {spec.label}{type_str}")


@provider_app.command()
def login(name: str) -> None:
    """Login to a provider (for OAuth based providers like Codex)."""
    from amberclaw.cli.oauth import (  # noqa: PLC0415 - load OAuth only for the explicit login command
        login_provider,
    )

    login_provider(name)
