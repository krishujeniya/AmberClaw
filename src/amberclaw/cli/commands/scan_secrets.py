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
    entropy: bool = typer.Option(
        False,
        "--entropy",
        "-e",
        help="Enable Shannon entropy analysis for high-entropy candidate secrets.",
    ),
    git_history: bool = typer.Option(
        False,
        "--git-history",
        "-g",
        help="Scan git commit diff history for committed and deleted credentials.",
    ),
) -> None:
    """
    Scan files for unredacted secrets/credentials.
    Exits with code 1 if any secrets are found.
    """
    cfg = load_config()
    scan_path = Path(path) if path else cfg.workspace_path

    console.print(f"[bold blue]Scanning {scan_path} for secrets...[/bold blue]")

    findings: list[dict] = []
    if git_history:
        findings.extend(
            SecretScanner.scan_git_history(scan_path, check_entropy=entropy)
        )
    elif scan_path.is_file():
        if scan_path.suffix in [".zip", ".tar", ".gz"]:
            findings.extend(
                SecretScanner.scan_archive(scan_path, check_entropy=entropy)
            )
        else:
            findings.extend(SecretScanner.scan_file(scan_path, check_entropy=entropy))
    else:
        findings.extend(SecretScanner.scan_workspace(scan_path, check_entropy=entropy))

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
        rel_path = f.get("file", f.get("member", "unknown"))
        line_info = str(f.get("line") or f.get("commit") or "-")
        with contextlib.suppress(Exception):
            rel_path = str(Path(rel_path).relative_to(scan_path.parent))

        table.add_row(
            rel_path,
            line_info,
            f.get("type", "Secret"),
            f.get("match_preview", "..."),
        )

    console.print(table)
    console.print(
        "\n[bold red]Action Required:[/bold red] Please encrypt these credentials using the Vault "
        "(e.g., prefixing them with 'vault://') or remove them from workspace files before committing."
    )
    raise typer.Exit(code=1)
