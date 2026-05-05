import typer
from rich.console import Console
from rich.table import Table
from amberclaw import __logo__

console = Console()

def usage(
    days: int = typer.Option(7, "--days", "-d", help="Number of days to show usage for"),
    all_time: bool = typer.Option(False, "--all", "-a", help="Show all-time usage"),
) -> None:
    """Show token usage and cost monitoring dashboard."""
    from amberclaw.utils import cost_tracker

    costs = cost_tracker.get_total_costs(days=None if all_time else days)

    console.print(f"{__logo__} [bold cyan]Token Usage Dashboard[/bold cyan]\n")
    if all_time:
        console.print("[dim]Period: All Time[/dim]\n")
    else:
        console.print(f"[dim]Period: Last {days} days[/dim]\n")

    if not costs:
        console.print("[yellow]No usage data found.[/yellow]")
        return

    table = Table(box=None, header_style="bold blue")
    table.add_column("Model", style="cyan")
    table.add_column("Calls", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Cost ($)", justify="right", style="green")
    table.add_column("Avg Latency", justify="right", style="dim")

    total_calls = 0
    total_tokens = 0
    total_cost = 0.0

    sorted_models = sorted(costs.items(), key=lambda x: x[1]["total_cost"], reverse=True)

    for model, data in sorted_models:
        table.add_row(
            model,
            str(data["calls"]),
            f"{data['total_tokens']:,}",
            f"${data['total_cost']:.4f}",
            f"{data['avg_latency_ms']:.0f}ms",
        )
        total_calls += data["calls"]
        total_tokens += data["total_tokens"]
        total_cost += data["total_cost"]

    table.add_section()
    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{total_calls}[/bold]",
        f"[bold]{total_tokens:,}[/bold]",
        f"[bold]${total_cost:.4f}[/bold]",
        "",
    )

    console.print(table)
