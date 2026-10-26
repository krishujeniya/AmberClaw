"""Disaster recovery and state restoration CLI commands."""

from pathlib import Path

import typer

from amberclaw.storage.backup import DisasterRecoveryManager

from .utils import console

restore_app = typer.Typer(help="Restore AmberClaw state from backup archives")


@restore_app.command("run")
def restore_run(
    archive: Path = typer.Argument(..., help="Path to the .tar.gz backup archive"),
    target_dir: Path | None = typer.Option(
        None, "--target-dir", "-t", help="Target directory for restored data"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force overwrite existing destination files"
    ),
) -> None:
    """Safely restore AmberClaw database and state files from a verified backup archive."""
    console.print(f"[bold blue]Restoring AmberClaw state from {archive}...[/bold blue]")
    mgr = DisasterRecoveryManager()
    try:
        manifest = mgr.restore_backup(
            archive_path=archive, target_dir=target_dir, force=force
        )
        console.print(
            f"[bold green]✓ Restoration Complete:[/bold green] Restored {manifest.total_files} files "
            f"from backup '{manifest.backup_id}'."
        )
    except Exception as e:
        console.print(f"[bold red]✗ Restoration Failed:[/bold red] {e}")
        raise typer.Exit(code=1) from e
