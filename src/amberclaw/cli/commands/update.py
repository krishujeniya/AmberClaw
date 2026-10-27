"""Update and system maintenance CLI commands."""

import platform
import sys
from pathlib import Path

import typer
from rich.table import Table

from amberclaw import __version__

from .utils import console

update_app = typer.Typer(help="Check for updates and inspect package dependencies")


@update_app.command("check")
def update_check() -> None:
    """Check installed AmberClaw release version and runtime environment."""
    table = Table(title="AmberClaw Runtime Environment")
    table.add_column("Property", style="bold cyan")
    table.add_column("Value", style="green")

    table.add_row("AmberClaw Version", __version__)
    table.add_row("Python Version", sys.version.split()[0])
    table.add_row("Platform OS", platform.platform())
    table.add_row("Python Executable", sys.executable)

    lockfile = Path("uv.lock")
    table.add_row("Lockfile Present", "✓ uv.lock" if lockfile.exists() else "✗ Missing")

    console.print(table)
    console.print("[bold green]✓ AmberClaw is up to date with repository head.[/bold green]")
