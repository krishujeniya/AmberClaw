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
    blueprint,
    budget,
    channels,
    company,
    council,
    cron,
    db,
    doctor,
    gateway,
    ingest,
    logs,
    mythos,
    onboard,
    org,
    pair,
    policy,
    provider,
    restore,
    scan_secrets,
    skills,
    status,
    ticket,
    tui,
    update,
    web,
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
app.add_typer(blueprint.blueprint_app, name="blueprint")
app.add_typer(policy.policy_app, name="policy")
app.add_typer(ticket.ticket_app, name="ticket")
app.add_typer(cron.cron_app, name="cron")
app.add_typer(logs.logs_app, name="logs")
app.add_typer(web.web_app, name="web")
app.add_typer(update.update_app, name="update")
app.add_typer(company.company_app, name="company")
from amberclaw.cli.oauth import oauth_app

app.add_typer(oauth_app, name="oauth")


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
