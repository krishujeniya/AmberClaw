import typer
from rich.console import Console
from amberclaw import __logo__
from amberclaw.config import loader

console = Console()

def status() -> None:
    """Show amberclaw status."""
    config_path = loader.get_config_path()
    cfg = loader.load_config()
    workspace = cfg.workspace_path

    console.print(f"{__logo__} amberclaw Status\n")

    console.print(
        f"Config: {config_path} {'[green]✓[/green]' if config_path.exists() else '[red]✗[/red]'}"
    )
    console.print(
        f"Workspace: {workspace} {'[green]✓[/green]' if workspace.exists() else '[red]✗[/red]'}"
    )

    if config_path.exists():
        from amberclaw.providers.registry import PROVIDERS

        console.print(f"Model: {cfg.agents.defaults.model}")

        # Check API keys from registry
        for spec in PROVIDERS:
            p = getattr(cfg.providers, spec.name, None)
            if p is None:
                continue
            if spec.is_oauth:
                console.print(f"{spec.label}: [green]✓ (OAuth)[/green]")
            elif spec.is_local:
                # Local deployments show api_base instead of api_key
                if p.api_base:
                    console.print(f"{spec.label}: [green]✓ {p.api_base}[/green]")
                else:
                    console.print(f"{spec.label}: [dim]not set[/dim]")
            else:
                has_key = bool(p.api_key)
                console.print(
                    f"{spec.label}: {'[green]✓[/green]' if has_key else '[dim]not set[/dim]'}"
                )
