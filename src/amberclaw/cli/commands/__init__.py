"""CLI commands for amberclaw."""

import typer
from amberclaw import __logo__, __version__
from . import utils
from .utils import console
from amberclaw.config.loader import get_config_path, load_config, save_config, load_runtime_config
from amberclaw.config.paths import get_workspace_path
from amberclaw.config.schema import Config
from amberclaw.providers.factory import make_provider
from amberclaw.utils.helpers import sync_workspace_templates

app = typer.Typer(
    name="amberclaw",
    help=f"{__logo__} AmberClaw - Personal AI Assistant",
    no_args_is_help=True,
)

from . import doctor, onboard, gateway, agent, status, budget, ingest, council, mythos, skills, channels, provider, pair, scan_secrets

# Register commands
app.command()(doctor.doctor)
app.command()(onboard.onboard)
app.command()(gateway.gateway)
app.command()(agent.agent)
app.command()(status.status)
app.command()(budget.usage)
app.command()(ingest.ingest)
app.command()(council.council)
app.command()(mythos.mythos)
app.command()(pair.pair)
app.command("scan-secrets")(scan_secrets.scan_secrets)

# Sub-apps
app.add_typer(skills.skills_app, name="skill")
app.add_typer(channels.channels_app, name="channels")
app.add_typer(provider.provider_app, name="provider")

# Callback for version
def version_callback(value: bool) -> None:
    if value:
        console.print(f"{__logo__} AmberClaw v{__version__}")
        raise typer.Exit()

@app.callback()
def main(
    version: bool = typer.Option(None, "--version", "-v", callback=version_callback, is_eager=True),
) -> None:
    """AmberClaw - Personal AI Assistant."""
    pass
