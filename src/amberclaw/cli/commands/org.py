"""Organizational hierarchy CLI commands."""

import typer
from rich.console import Console
from rich.table import Table

from amberclaw.org.agent_node import AgentNode
from amberclaw.org.chart import OrgChart
from amberclaw.org.permissions import OrgRole

org_app = typer.Typer(help="Manage organizational hierarchy, roles, and delegation policies.")
console = Console()


def _get_demo_org_chart() -> OrgChart:
    """Construct standard default org chart for CLI visualization."""
    chart = OrgChart()
    admin = AgentNode(id="admin", name="Executive Admin", role=OrgRole.ADMIN, department="executive")
    lead_eng = AgentNode(id="lead_eng", name="Engineering Lead", role=OrgRole.DEPARTMENT_LEAD, department="engineering", manager_id="admin")
    dev_agent = AgentNode(id="dev_1", name="Senior Developer", role=OrgRole.STAFF_AGENT, department="engineering", manager_id="lead_eng")
    qa_agent = AgentNode(id="qa_1", name="QA Specialist", role=OrgRole.SPECIALIST_AGENT, department="engineering", manager_id="lead_eng")
    sales_lead = AgentNode(id="lead_sales", name="Sales Lead", role=OrgRole.DEPARTMENT_LEAD, department="sales", manager_id="admin")

    chart.add_agent(admin)
    chart.add_agent(lead_eng)
    chart.add_agent(dev_agent)
    chart.add_agent(qa_agent)
    chart.add_agent(sales_lead)
    return chart


@org_app.command("show")
def show_org() -> None:
    """Display active organizational hierarchy."""
    chart = _get_demo_org_chart()

    table = Table(title="🐾 AmberClaw Organizational Hierarchy")
    table.add_column("Agent ID", style="bold cyan")
    table.add_column("Name", style="white")
    table.add_column("Role", style="yellow")
    table.add_column("Department", style="magenta")
    table.add_column("Manager", style="dim")
    table.add_column("Subordinates", style="green")

    for node in chart.nodes.values():
        table.add_row(
            node.id,
            node.name,
            node.role.value,
            node.department,
            node.manager_id or "Root",
            ", ".join(node.subordinate_ids) or "None",
        )

    console.print(table)


@org_app.command("delegate")
def check_delegation(
    from_agent: str = typer.Argument(..., help="Delegating agent ID"),
    to_agent: str = typer.Argument(..., help="Target subordinate agent ID"),
) -> None:
    """Evaluate if an agent has permission to delegate to another."""
    chart = _get_demo_org_chart()
    allowed = chart.can_delegate(from_agent, to_agent)

    if allowed:
        console.print(f"[bold green]✔ Delegation ALLOWED:[/bold green] Agent '{from_agent}' can delegate tasks to '{to_agent}'.")
    else:
        console.print(f"[bold red]✖ Delegation DENIED:[/bold red] Agent '{from_agent}' cannot delegate tasks to '{to_agent}'.")


@org_app.command("escalate")
def show_escalation(
    agent_id: str = typer.Argument(..., help="Agent ID to trace escalation path"),
) -> None:
    """Trace the escalation chain of command from an agent up to executive admin."""
    chart = _get_demo_org_chart()
    path = chart.get_escalation_path(agent_id)

    if not path:
        console.print(f"Agent '{agent_id}' has no higher escalation manager.")
        return

    console.print(f"[bold]Escalation chain for '{agent_id}':[/bold]")
    for i, mgr in enumerate(path, 1):
        console.print(f"  {i}. [cyan]{mgr.id}[/cyan] ({mgr.name}) - [yellow]{mgr.role.value}[/yellow] [{mgr.department}]")
