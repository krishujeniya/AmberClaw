# ruff: noqa: E402
"""CLI commands for amberclaw."""

import typer

from amberclaw import __logo__, __version__

from .utils import console

app = typer.Typer(
    name="amberclaw",
    help=f"{__logo__} AmberClaw - Personal AI Assistant",
    no_args_is_help=True,
)

from . import (
    agent,
    backup,
    budget,
    channels,
    council,
    db,
    doctor,
    gateway,
    ingest,
    mythos,
    onboard,
    org,
    pair,
    provider,
    restore,
    scan_secrets,
    skills,
    status,
    tui,
)

# Register commands
app.command()(doctor.doctor)
app.command()(onboard.onboard)
app.command("init")(onboard.onboard)
app.command()(gateway.gateway)
app.command()(agent.agent)
app.command()(status.status)
app.command()(budget.usage)
app.command()(ingest.ingest)
app.command()(council.council)
app.command()(mythos.mythos)
app.command()(pair.pair)
app.command("scan-secrets")(scan_secrets.scan_secrets)
app.command("tui")(tui.run_tui)

# Sub-apps
app.add_typer(skills.skills_app, name="skill")
app.add_typer(channels.channels_app, name="channels")
app.add_typer(provider.provider_app, name="provider")
app.add_typer(org.org_app, name="org")
app.add_typer(db.db_app, name="db")
app.add_typer(backup.backup_app, name="backup")
app.add_typer(restore.restore_app, name="restore")


# Callback for version
def version_callback(value: bool) -> None:
    if value:
        console.print(f"{__logo__} AmberClaw v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
) -> None:
    """AmberClaw - Personal AI Assistant."""
    pass


__all__ = ["app"]
