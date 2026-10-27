"""System health check and diagnostic tool."""

import importlib.metadata
import os

from rich.console import Console
from rich.table import Table

from amberclaw.config.loader import get_config_path, load_config
from amberclaw.security.enclave.diagnostics import get_enclave_diagnostics

console = Console()


def run_doctor() -> None:
    """Run system diagnostics."""
    console.print("[bold cyan]AmberClaw Health Check[/bold cyan]\n")

    # 1. Config Check
    config_path = get_config_path()
    status_config = (
        "[green]OK[/green]"
        if config_path.exists()
        else "[yellow]NOT FOUND (Using Defaults)[/yellow]"
    )
    console.print(f"• Config Path: {config_path} ({status_config})")

    # 2. Workspace Check
    config = load_config()
    workspace = config.workspace_path
    if workspace.exists():
        status_ws = "[green]OK[/green]"
    else:
        try:
            workspace.mkdir(parents=True, exist_ok=True)
            status_ws = "[green]CREATED[/green]"
        except Exception as e:
            status_ws = f"[red]ERROR: {e}[/red]"
    console.print(f"• Workspace: {workspace.absolute()} ({status_ws})")

    # 3. API Key Check
    keys = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
        "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY"),
        "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY"),
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
    }

    table = Table(
        title="Environment & API Keys", show_header=True, header_style="bold magenta"
    )
    table.add_column("Key", style="dim")
    table.add_column("Found", justify="right")
    table.add_column("Source", justify="left")

    for name, val in keys.items():
        found = "✅" if val else "❌"
        source = "Environment" if val else "Missing"
        table.add_row(name, found, source)

    console.print(table)

    # 4. Core dependencies
    deps = ["litellm", "pydantic", "typer", "rich", "loguru"]
    dep_table = Table(
        title="Core Dependencies", show_header=True, header_style="bold blue"
    )
    dep_table.add_column("Package")
    dep_table.add_column("Version")

    for d in deps:
        try:
            ver = importlib.metadata.version(d)
            dep_table.add_row(d, f"[green]{ver}[/green]")
        except importlib.metadata.PackageNotFoundError:
            dep_table.add_row(d, "[red]NOT INSTALLED[/red]")

    console.print(dep_table)

    # 5. Hardware Enclaves & Confidential Computing
    diag = get_enclave_diagnostics()
    enclave_table = Table(
        title="Zero-Trust Enclaves & Confidential Computing",
        show_header=True,
        header_style="bold green",
    )
    enclave_table.add_column("Platform")
    enclave_table.add_column("Status", justify="right")
    enclave_table.add_column("Details", justify="left")

    for _plat_key, plat_info in diag["platforms"].items():
        name = plat_info["platform"]
        avail = plat_info.get("available", False)
        status_str = "✅ Available" if avail else "❌ Absent"
        details = plat_info.get("details", "")
        enclave_table.add_row(name, status_str, details)

    console.print(enclave_table)

    console.print(
        "\n[bold green]Ready to claw![/bold green]"
        if any(keys.values())
        else "\n[bold yellow]Ready, but no API keys found. Some features will fail.[/bold yellow]",
    )
