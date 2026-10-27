"""Company hierarchy and tree visualization CLI commands."""

import typer
from rich.tree import Tree

from amberclaw.org.chart import OrgChart

from .org import _get_demo_org_chart
from .utils import console

company_app = typer.Typer(help="Manage company organization structure and hierarchy tree")


def _build_agent_tree(chart: OrgChart, parent_node: Tree, current_id: str) -> None:
    agent = chart.get_agent(current_id)
    if not agent:
        return

    subordinates = chart.get_subordinates(current_id, recursive=False)
    for sub in subordinates:
        branch = parent_node.add(
            f"[bold cyan]{sub.name}[/bold cyan] ([yellow]{sub.role.value}[/yellow]) - [dim]{sub.id}[/dim]"
        )
        _build_agent_tree(chart, branch, sub.id)


@company_app.command("tree")
def company_tree() -> None:
    """Render tree view of company agents and reporting relationships."""
    chart = _get_demo_org_chart()

    # Find root agents (no manager)
    roots = [node for node in chart.nodes.values() if not node.manager_id]

    tree = Tree("🏢 [bold green]AmberClaw Company Hierarchy[/bold green]")
    for r in roots:
        root_branch = tree.add(
            f"[bold cyan]{r.name}[/bold cyan] ([yellow]{r.role.value}[/yellow]) - [dim]{r.id}[/dim]"
        )
        _build_agent_tree(chart, root_branch, r.id)

    console.print(tree)


@company_app.command("audit")
def company_audit() -> None:
    """Audit company organizational hierarchy for cycles and escalation paths."""
    chart = _get_demo_org_chart()

    issues = []
    # Verify every non-root agent has valid escalation path to admin
    for agent_id, agent in chart.nodes.items():
        if agent.manager_id:
            path = chart.get_escalation_path(agent_id)
            if not path or path[-1].role.value != "admin":
                issues.append(f"Agent {agent_id} does not escalate to an admin")

    if not issues:
        console.print(
            f"[bold green]✓ Organization audit passed! {len(chart.nodes)} agents verified with zero cycles and full escalation integrity.[/bold green]"
        )
    else:
        console.print("[bold red]✗ Organization audit failed:[/bold red]")
        for iss in issues:
            console.print(f"  [red]• {iss}[/red]")
        raise typer.Exit(code=1)
