import typer
from rich.console import Console
from amberclaw import __logo__
from amberclaw.config import loader, paths, schema
from amberclaw.utils import helpers

console = Console()

def onboard() -> None:
    """Initialize AmberClaw configuration and workspace."""
    config_path = loader.get_config_path()

    if config_path.exists():
        console.print(f"[yellow]Config already exists at {config_path}[/yellow]")
        console.print("  [bold]y[/bold] = overwrite with defaults (existing values will be lost)")
        console.print(
            "  [bold]N[/bold] = refresh config, keeping existing values and adding new fields"
        )
        if typer.confirm("Overwrite?"):
            config = schema.Config()
            loader.save_config(config)
            console.print(f"[green]✓[/green] Config reset to defaults at {config_path}")
        else:
            config = loader.load_config()
            loader.save_config(config)
            console.print(
                f"[green]✓[/green] Config refreshed at {config_path} (existing values preserved)"
            )
    else:
        loader.save_config(schema.Config())
        console.print(f"[green]✓[/green] Created config at {config_path}")

    # Create workspace
    workspace = paths.get_workspace_path()

    if not workspace.exists():
        workspace.mkdir(parents=True, exist_ok=True)
        console.print(f"[green]✓[/green] Created workspace at {workspace}")

    helpers.sync_workspace_templates(workspace)

    console.print(f"\n{__logo__} AmberClaw is ready!")
    console.print("\nNext steps:")
    console.print("  1. Add your API key to [cyan]~/.amberclaw/config.json[/cyan]")
    console.print("     Get one at: https://openrouter.ai/keys")
    console.print('  2. Chat: [cyan]amberclaw agent -m "Hello!"[/cyan]')
    console.print(
        "\n[dim]Want Telegram/WhatsApp? See: https://github.com/krishujeniya/AmberClaw#-chat-apps[/dim]"
    )
