"""Cron and scheduled tasks management CLI commands."""

from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.table import Table

from amberclaw.cron.service import CronService

from .utils import console

cron_app = typer.Typer(help="Manage cron jobs and scheduled agent tasks")


def _get_cron_service() -> CronService:
    store_path = Path("~/.amberclaw/cron_jobs.json").expanduser()
    store_path.parent.mkdir(parents=True, exist_ok=True)
    return CronService(store_path=store_path)


@cron_app.command("list")
def cron_list(
    all_jobs: bool = typer.Option(
        False, "--all", "-a", help="Include disabled jobs in the list"
    ),
) -> None:
    """List all scheduled cron jobs."""
    service = _get_cron_service()
    jobs = service.list_jobs(include_disabled=all_jobs)

    if not jobs:
        console.print("[yellow]No scheduled jobs found.[/yellow]")
        return

    table = Table(title="Scheduled Cron Jobs")
    table.add_column("Job ID", style="bold cyan")
    table.add_column("Name", style="white")
    table.add_column("Schedule", style="yellow")
    table.add_column("Next Run", style="green")
    table.add_column("Enabled", style="magenta")

    for j in jobs:
        sched_desc = (
            j.schedule.expr
            if j.schedule.kind == "cron"
            else f"every {j.schedule.every_ms // 1000}s"
            if j.schedule.kind == "every" and j.schedule.every_ms
            else j.schedule.kind
        )
        next_run_str = (
            datetime.fromtimestamp(j.state.next_run_ms / 1000, tz=UTC).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            if j.state.next_run_ms
            else "Never"
        )
        table.add_row(
            j.id[:8] + "...",
            j.name,
            sched_desc,
            next_run_str,
            "✓ Yes" if j.enabled else "✗ No",
        )

    console.print(table)


@cron_app.command("status")
def cron_status() -> None:
    """Show operational status of the cron service."""
    service = _get_cron_service()
    stat = service.status()

    table = Table(title="Cron Service Status")
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value", style="green")

    table.add_row("Running", "✓ Yes" if stat.get("running") else "✗ Stopped")
    table.add_row("Total Jobs", str(stat.get("job_count", 0)))
    table.add_row("Enabled Jobs", str(stat.get("enabled_job_count", 0)))

    next_wake = stat.get("next_wake_ms")
    next_wake_str = (
        datetime.fromtimestamp(next_wake / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
        if next_wake
        else "None"
    )
    table.add_row("Next Wake", next_wake_str)

    console.print(table)


@cron_app.command("enable")
def cron_enable(job_id: str = typer.Argument(..., help="Job ID to enable")) -> None:
    """Enable a scheduled cron job."""
    service = _get_cron_service()
    job = service.enable_job(job_id, enabled=True)
    if job:
        console.print(f"[bold green]✓ Job '{job.name}' ({job_id}) enabled.[/bold green]")
    else:
        console.print(f"[bold red]Job not found: {job_id}[/bold red]")
        raise typer.Exit(code=1)


@cron_app.command("disable")
def cron_disable(job_id: str = typer.Argument(..., help="Job ID to disable")) -> None:
    """Disable a scheduled cron job."""
    service = _get_cron_service()
    job = service.enable_job(job_id, enabled=False)
    if job:
        console.print(f"[bold yellow]Job '{job.name}' ({job_id}) disabled.[/bold yellow]")
    else:
        console.print(f"[bold red]Job not found: {job_id}[/bold red]")
        raise typer.Exit(code=1)


@cron_app.command("remove")
def cron_remove(job_id: str = typer.Argument(..., help="Job ID to remove")) -> None:
    """Remove a scheduled cron job."""
    service = _get_cron_service()
    if service.remove_job(job_id):
        console.print(f"[bold green]✓ Job {job_id} removed.[/bold green]")
    else:
        console.print(f"[bold red]Job not found: {job_id}[/bold red]")
        raise typer.Exit(code=1)
