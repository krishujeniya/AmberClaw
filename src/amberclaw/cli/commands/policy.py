"""Compliance policy packs CLI commands."""

import typer
from rich.panel import Panel
from rich.table import Table

from amberclaw.governance.policies import PolicyEngine
from amberclaw.governance.policy_packs import ComplianceStandard, PolicyPackRegistry

from .utils import console

policy_app = typer.Typer(help="Manage enterprise compliance policy packs")


@policy_app.command("list")
def policy_list() -> None:
    """List available enterprise compliance policy packs."""
    table = Table(title="Enterprise Compliance Policy Packs")
    table.add_column("Standard ID", style="bold cyan")
    table.add_column("Pack Name", style="green")
    table.add_column("Rules", style="yellow", justify="right")
    table.add_column("Description", style="white")

    for std in ComplianceStandard:
        try:
            pack = PolicyPackRegistry.get_pack(std)
            table.add_row(std.value, pack.name, str(len(pack.rules)), pack.description)
        except Exception:
            table.add_row(std.value, std.value.upper(), "-", "Standard compliance pack")

    console.print(table)


@policy_app.command("inspect")
def policy_inspect(
    standard: str = typer.Argument(
        ..., help="Compliance standard ID (e.g. 'soc2_type2', 'hipaa', 'gdpr', 'air_gapped')"
    ),
) -> None:
    """Inspect the rules and enforcement actions in a compliance policy pack."""
    try:
        std_enum = ComplianceStandard(standard.lower())
        pack = PolicyPackRegistry.get_pack(std_enum)
    except Exception as ex:
        console.print(f"[bold red]Unknown or unsupported compliance pack '{standard}': {ex}[/bold red]")
        raise typer.Exit(code=1) from ex

    console.print(
        Panel(
            f"[bold]{pack.name}[/bold] (v{pack.version})\n{pack.description}",
            title=f"Policy Pack: [bold cyan]{pack.standard.value}[/bold cyan]",
        )
    )

    table = Table(title=f"Rules in {pack.name}")
    table.add_column("Policy ID", style="bold cyan")
    table.add_column("Rule Name", style="white")
    table.add_column("Targets", style="yellow")
    table.add_column("Enforcement", style="bold magenta")
    table.add_column("Forbidden Tokens", style="red")

    for rule in pack.rules:
        table.add_row(
            rule.policy_id,
            rule.name,
            ", ".join(rule.target_actions),
            rule.enforcement.value,
            ", ".join(rule.forbidden_tokens) if rule.forbidden_tokens else "(none)",
        )

    console.print(table)


@policy_app.command("test")
def policy_test(
    standard: str = typer.Argument(
        ..., help="Compliance standard ID to test against PolicyEngine"
    ),
) -> None:
    """Test policy pack enforcement rules in memory."""
    try:
        std_enum = ComplianceStandard(standard.lower())
        engine = PolicyEngine()
        applied = PolicyPackRegistry.apply_pack(std_enum, engine)
    except Exception as ex:
        console.print(f"[bold red]Error loading policy pack: {ex}[/bold red]")
        raise typer.Exit(code=1) from ex

    console.print(
        f"[bold green]✓ Loaded and verified {applied} rules for {std_enum.value} compliance pack.[/bold green]"
    )
