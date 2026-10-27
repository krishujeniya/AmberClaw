"""Database schema migrations CLI commands."""

import typer

from amberclaw.database.migrator import (
    apply_migrations,
    get_current_revision,
    rollback_migrations,
)

from .utils import console

db_app = typer.Typer(help="Manage AmberClaw database schema migrations")


@db_app.command("upgrade")
def db_upgrade(
    revision: str = typer.Option(
        "head", "--revision", "-r", help="Target migration revision (default: head)"
    ),
    db_url: str | None = typer.Option(
        None, "--db-url", help="Database connection URL override"
    ),
) -> None:
    """Apply database schema migrations to the specified revision."""
    console.print(
        f"[bold blue]Running database migrations to '{revision}'...[/bold blue]"
    )
    success = apply_migrations(target_revision=revision, db_url=db_url)
    if success:
        current = get_current_revision(db_url=db_url)
        console.print(
            f"[green]✓ Database migrated successfully. Current revision: {current}[/green]"
        )
    else:
        console.print("[red]✗ Migration failed. Check logs for details.[/red]")
        raise typer.Exit(code=1)


@db_app.command("rollback")
def db_rollback(
    revision: str = typer.Option(
        "base", "--revision", "-r", help="Target rollback revision (default: base)"
    ),
    db_url: str | None = typer.Option(
        None, "--db-url", help="Database connection URL override"
    ),
) -> None:
    """Rollback database schema migrations to the specified revision."""
    console.print(
        f"[yellow]Rolling back database migrations to '{revision}'...[/yellow]"
    )
    success = rollback_migrations(target_revision=revision, db_url=db_url)
    if success:
        current = get_current_revision(db_url=db_url)
        console.print(
            f"[green]✓ Database rollback completed. Current revision: {current}[/green]"
        )
    else:
        console.print("[red]✗ Rollback failed. Check logs for details.[/red]")
        raise typer.Exit(code=1)


@db_app.command("current")
def db_current(
    db_url: str | None = typer.Option(
        None, "--db-url", help="Database connection URL override"
    ),
) -> None:
    """Show the currently applied database schema migration revision."""
    current = get_current_revision(db_url=db_url)
    if current:
        console.print(f"[bold green]Current applied revision:[/bold green] {current}")
    else:
        console.print(
            "[yellow]No database migrations applied or database not initialized.[/yellow]"
        )
