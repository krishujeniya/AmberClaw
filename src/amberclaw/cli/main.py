import typer
import uvicorn
from rich.console import Console
from amberclaw.cli.commands import app

console = Console()

@app.command()
def start(
    host: str = typer.Option("127.0.0.1", help="Host IP to bind the OS Gateway to."),
    port: int = typer.Option(8000, help="Port to run the gateway on."),
    reload: bool = typer.Option(False, help="Enable auto-reload for development."),
):
    """
    Starts the AmberClaw AI OS core engine and API Gateway.
    """
    console.print(f"[bold green]Starting AmberClaw AI OS on {host}:{port}...[/bold green]")
    # uvicorn run points to our FastAPI app
    uvicorn.run("amberclaw.api.main:app", host=host, port=port, reload=reload)

if __name__ == "__main__":
    app()
