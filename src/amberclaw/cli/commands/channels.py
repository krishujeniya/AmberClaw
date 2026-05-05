import typer
from rich.console import Console
from rich.table import Table
from amberclaw import __logo__
from amberclaw.config import loader, paths

channels_app = typer.Typer(help="Manage communication channels (Telegram, WhatsApp, etc).")
console = Console()

@channels_app.command()
def list():
    """List available and active channels."""
    cfg = loader.load_config()
    
    table = Table(title="Communication Channels", box=None)
    table.add_column("Channel", style="cyan")
    table.add_column("Status", style="bold")
    
    for channel_name, channel_cfg in cfg.channels.items():
        enabled = getattr(channel_cfg, "enabled", False)
        status = "[green]Enabled[/green]" if enabled else "[dim]Disabled[/dim]"
        table.add_row(channel_name.capitalize(), status)
        
    console.print(table)

@channels_app.command()
def setup(channel: str):
    """Set up a communication channel."""
    console.print(f"[bold cyan]Setting up {channel} channel...[/bold cyan]")
    # Placeholder for bridge installation/setup logic
    bridge_dir = paths.get_bridge_install_dir()
    console.print(f"Bridge directory: {bridge_dir}")
