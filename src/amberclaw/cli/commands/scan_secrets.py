import contextlib
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from amberclaw.config.loader import load_config
from amberclaw.security.secret_scanner import SecretScanner

console = Console()


def scan_secrets(
    path: str = typer.Option(
        None,
        "--path",
        "-p",
        help="Path to scan for secrets (defaults to active workspace).",
    ),
) -> None:
    """
    Scan files for unredacted secrets/credentials.
    Exits with code 1 if any secrets are found.
    """
    cfg = load_config()
    scan_path = Path(path) if path else cfg.workspace_path

    console.print(f"[bold blue]Scanning {scan_path} for secrets...[/bold blue]")

    if scan_path.is_file():
        findings = SecretScanner.scan_file(scan_path)
    else:
        findings = SecretScanner.scan_workspace(scan_path)

    if not findings:
        console.print("[bold green]✓ No secrets found in workspace![/bold green]")
        raise typer.Exit(code=0)

    console.print(
        f"[bold red]✗ Found {len(findings)} potential secret(s) in workspace:[/bold red]\n"
    )

    table = Table(title="Secret Scanner Findings")
    table.add_column("File", style="cyan")
    table.add_column("Line", style="magenta")
    table.add_column("Type", style="yellow")
    table.add_column("Preview", style="green")

    for f in findings:
        rel_path = f["file"]
        with contextlib.suppress(ValueError):
            # Try to show path relative to the scanned directory
            rel_path = str(Path(f["file"]).relative_to(scan_path.parent))

        table.add_row(
            rel_path,
            str(f["line"]),
            f["type"],
            f["match_preview"],
        )

    console.print(table)
    console.print(
        "\n[bold red]Action Required:[/bold red] Please encrypt these credentials using the Vault "
        "(e.g., prefixing them with 'vault://') or remove them from workspace files before committing."
    )
    raise typer.Exit(code=1)
