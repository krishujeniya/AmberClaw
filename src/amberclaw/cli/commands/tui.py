"""TUI CLI command handler."""

import typer
from rich.console import Console

from amberclaw.tui.app import AmberClawTUIApp

console = Console()


def run_tui(
    theme: str = typer.Option("default", "--theme", "-t", help="TUI theme (default, light, ocean)"),
    session: str = typer.Option("cli:direct", "--session", "-s", help="Session ID"),
) -> None:
    """Launch the split-pane AmberClaw Terminal User Interface."""
    tui_app = AmberClawTUIApp(theme_name=theme, console=console)
    tui_app.state.session_id = session
    console.print(tui_app.build_layout())
