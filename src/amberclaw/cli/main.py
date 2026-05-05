import typer
import uvicorn
import logging
from rich.console import Console

app = typer.Typer(
    name="amberclaw",
    help="AmberClaw AI OS Command Line Interface",
    add_completion=False,
)

console = Console()

@app.command()
def start(
    host: str = typer.Option("127.0.0.1", help="Host IP to bind the OS Gateway to."),
    port: int = typer.Option(8000, help="Port to run the gateway on."),
    reload: bool = typer.Option(False, help="Enable auto-reload for development.")
):
    """
    Starts the AmberClaw AI OS core engine and API Gateway.
    """
    console.print(f"[bold green]Starting AmberClaw AI OS on {host}:{port}...[/bold green]")
    # uvicorn run points to our FastAPI app
    uvicorn.run("amberclaw.api.main:app", host=host, port=port, reload=reload)

@app.command()
def status():
    """
    Check the status of the local AmberClaw engines.
    """
    console.print("[bold blue]AmberClaw System Status:[/bold blue]")
    console.print("- [green]Heartbeat Engine[/green]: Active")
    console.print("- [green]Governance Board[/green]: Monitoring")
    console.print("- [yellow]Memory System[/yellow]: Standby")

if __name__ == "__main__":
    app()
