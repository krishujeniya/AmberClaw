"""Disaster recovery and backup CLI commands."""

from pathlib import Path

import typer
from rich.table import Table

from amberclaw.storage.backup import DisasterRecoveryManager

from .utils import console

backup_app = typer.Typer(help="Manage AmberClaw backups and disaster recovery drills")


@backup_app.command("create")
def backup_create(
    name: str | None = typer.Option(
        None, "--name", "-n", help="Optional name for the backup archive"
    ),
    data_dir: Path = typer.Option(
        Path("data"), "--data-dir", help="AmberClaw data directory"
    ),
    backup_dir: Path = typer.Option(
        Path("backups"), "--backup-dir", help="Directory to store backup archives"
    ),
) -> None:
    """Create a point-in-time backup archive of AmberClaw state."""
    console.print("[bold blue]Starting AmberClaw state backup...[/bold blue]")
    mgr = DisasterRecoveryManager(data_dir=data_dir, backup_dir=backup_dir)
    try:
        archive_path = mgr.create_backup(name=name)
        console.print(f"[green]✓ Backup created successfully:[/green] {archive_path}")
    except Exception as e:
        console.print(f"[red]✗ Backup creation failed:[/red] {e}")
        raise typer.Exit(code=1) from e


@backup_app.command("list")
def backup_list(
    backup_dir: Path = typer.Option(
        Path("backups"), "--backup-dir", help="Directory containing backup archives"
    ),
) -> None:
    """List available state backup archives."""
    mgr = DisasterRecoveryManager(backup_dir=backup_dir)
    backups = mgr.list_backups()

    if not backups:
        console.print("[yellow]No backup archives found in[/yellow] " + str(backup_dir))
        return

    table = Table(title="AmberClaw State Backups")
    table.add_column("Backup ID", style="cyan")
    table.add_column("Created At", style="green")
    table.add_column("Files", justify="right")
    table.add_column("Size (Bytes)", justify="right")
    table.add_column("Archive Exists", justify="center")

    for b in backups:
        exists_mark = "[green]✓[/green]" if b.get("archive_exists") else "[red]✗[/red]"
        table.add_row(
            b.get("backup_id", "unknown"),
            b.get("created_at", "unknown"),
            str(b.get("total_files", 0)),
            f"{b.get('total_size_bytes', 0):,}",
            exists_mark,
        )

    console.print(table)


@backup_app.command("drill")
def backup_drill(
    data_dir: Path = typer.Option(
        Path("data"), "--data-dir", help="AmberClaw data directory to test"
    ),
    backup_dir: Path = typer.Option(
        Path("backups"),
        "--backup-dir",
        help="Directory to store temporary drill artifacts",
    ),
) -> None:
    """Execute an automated Disaster Recovery drill verifying database restoration and integrity."""
    console.print(
        "[bold blue]Initiating automated Disaster Recovery drill...[/bold blue]"
    )
    mgr = DisasterRecoveryManager(data_dir=data_dir, backup_dir=backup_dir)
    result = mgr.run_dr_drill()

    if result.success:
        console.print(
            f"[bold green]✓ DR Drill Passed ({result.duration_seconds}s)[/bold green]\n"
            f"  - Databases Verified: {result.databases_checked}\n"
            f"  - Records Checked: {result.records_checked}"
        )
    else:
        console.print(
            f"[bold red]✗ DR Drill Failed ({result.duration_seconds}s):[/bold red] {result.error}"
        )
        raise typer.Exit(code=1)
