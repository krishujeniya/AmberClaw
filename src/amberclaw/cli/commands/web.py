"""Mission control web dashboard CLI commands."""

import httpx
import typer
import uvicorn
from rich.panel import Panel

from .utils import console

HTTP_OK = 200

web_app = typer.Typer(help="Manage AmberClaw Mission Control web dashboard")


@web_app.command("start")
def web_start(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Bind host for web server"),
    port: int = typer.Option(8080, "--port", "-p", help="Port for web dashboard"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable hot reload for development"),
) -> None:
    """Start the AmberClaw Mission Control web dashboard."""
    console.print(
        Panel(
            f"Starting [bold cyan]AmberClaw Mission Control[/bold cyan] at [bold green]http://{host}:{port}[/bold green]",
            title="AmberClaw Web Dashboard",
        )
    )
    uvicorn.run("amberclaw.web.server:create_web_app", host=host, port=port, reload=reload, factory=True)


@web_app.command("status")
def web_status(
    url: str = typer.Option("http://127.0.0.1:8080/api/dashboard/summary", "--url", "-u", help="Health probe URL"),
) -> None:
    """Check if the web dashboard is running and reachable."""
    try:
        resp = httpx.get(url, timeout=3.0)
        if resp.status_code == HTTP_OK:
            console.print(f"[bold green]✓ Web dashboard is healthy and responding at {url}[/bold green]")
        else:
            console.print(f"[yellow]Dashboard returned status {resp.status_code} at {url}[/yellow]")
    except Exception as ex:
        console.print(f"[bold red]✗ Web dashboard is unreachable at {url}: {ex}[/bold red]")
        raise typer.Exit(code=1) from ex
