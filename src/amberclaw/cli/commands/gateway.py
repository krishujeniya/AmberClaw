"""
AmberClaw CLI Gateway Command
"""
import typer
import uvicorn
from amberclaw.config.schema import settings

app = typer.Typer(help="Manage the AmberClaw API Gateway")


@app.command()
def start(
    host: str = typer.Option(settings.api_host, help="Host to bind the gateway to"),
    port: int = typer.Option(settings.api_port, help="Port to bind the gateway to"),
    reload: bool = typer.Option(settings.debug, help="Enable auto-reload for development"),
):
    """Start the AmberClaw API Gateway."""
    typer.echo(f"Starting AmberClaw Gateway at http://{host}:{port}")
    uvicorn.run(
        "amberclaw.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
