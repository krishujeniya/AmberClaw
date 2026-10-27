"""Audit logs inspection and cryptographic verification CLI commands."""

import json
from pathlib import Path

import typer
from rich.table import Table

from amberclaw.security.audit import SecurityAuditLogger

from .utils import console

logs_app = typer.Typer(help="Inspect and verify tamper-evident security audit logs")


def _get_audit_log_path(custom_path: Path | None = None) -> Path:
    if custom_path:
        return custom_path
    default_path = Path("logs/audit.jsonl")
    if default_path.exists():
        return default_path
    # Fallback to user home
    home_path = Path("~/.amberclaw/audit.jsonl").expanduser()
    if home_path.exists():
        return home_path
    return default_path


@logs_app.command("tail")
def logs_tail(
    lines: int = typer.Option(20, "--lines", "-n", help="Number of recent log lines to display"),
    log_file: Path | None = typer.Option(
        None, "--file", "-f", help="Path to audit.jsonl log file"
    ),
    actor: str | None = typer.Option(
        None, "--actor", "-a", help="Filter by actor identifier"
    ),
) -> None:
    """Tail recent entries from the security audit log."""
    path = _get_audit_log_path(log_file)
    if not path.exists():
        console.print(f"[yellow]No audit log file found at {path}[/yellow]")
        return

    raw_lines = path.read_text(encoding="utf-8").strip().splitlines()
    entries = []
    for line in raw_lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            if actor and entry.get("actor") != actor:
                continue
            entries.append(entry)
        except json.JSONDecodeError:
            continue

    recent = entries[-lines:]
    if not recent:
        console.print("[yellow]No audit log entries found matching criteria.[/yellow]")
        return

    table = Table(title=f"Security Audit Log (Last {len(recent)} entries)")
    table.add_column("Idx", style="dim", justify="right")
    table.add_column("Timestamp", style="cyan")
    table.add_column("Actor", style="bold green")
    table.add_column("Action", style="yellow")
    table.add_column("Outcome", style="magenta")
    table.add_column("Details", style="white")

    for e in recent:
        outcome = e.get("outcome", "unknown")
        outcome_style = "[bold green]✓ success[/bold green]" if outcome == "success" else f"[bold red]✗ {outcome}[/bold red]"
        table.add_row(
            str(e.get("index", "-")),
            str(e.get("timestamp", "-"))[:19],
            str(e.get("actor", "-")),
            str(e.get("action", "-")),
            outcome_style,
            str(e.get("metadata", ""))[:40],
        )

    console.print(table)


@logs_app.command("verify")
def logs_verify(
    log_file: Path | None = typer.Option(
        None, "--file", "-f", help="Path to audit.jsonl log file to verify"
    ),
) -> None:
    """Verify cryptographic SHA-256 hash chain integrity of the audit log."""
    path = _get_audit_log_path(log_file)
    if not path.exists():
        console.print(f"[bold red]Audit log file not found at {path}[/bold red]")
        raise typer.Exit(code=1)

    logger_inst = SecurityAuditLogger(log_dir=path.parent)
    is_valid = logger_inst.verify_integrity(target_file=path)

    if is_valid:
        console.print(
            f"[bold green]✓ Audit log integrity verified! All SHA-256 hash-chains intact at {path}.[/bold green]"
        )
    else:
        console.print(
            f"[bold red]✗ TAMPER DETECTED: Audit log hash chain verification failed at {path}.[/bold red]"
        )
        raise typer.Exit(code=1)
