"""Governance ticket management CLI commands."""

import typer
from rich.panel import Panel
from rich.table import Table

from amberclaw.governance.tickets import TicketPriority, TicketStatus, TicketSystem

from .utils import console

ticket_app = typer.Typer(help="Manage human-in-the-loop governance approval tickets")


DESC_TRUNCATE_LIMIT = 40


@ticket_app.command("list")
def ticket_list(
    status: str | None = typer.Option(
        None, "--status", "-s", help="Filter by status: pending, approved, rejected"
    ),
    priority: str | None = typer.Option(
        None, "--priority", "-p", help="Filter by priority: low, medium, high, critical"
    ),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of tickets to display"),
) -> None:
    """List governance approval tickets."""
    system = TicketSystem()
    status_filter = TicketStatus(status.lower()) if status else None
    priority_filter = TicketPriority(priority.lower()) if priority else None

    tickets = system.list_tickets(status=status_filter, priority=priority_filter)[:limit]

    if not tickets:
        console.print("[yellow]No tickets found matching criteria.[/yellow]")
        return

    table = Table(title="Governance Approval Tickets")
    table.add_column("Ticket ID", style="bold cyan")
    table.add_column("Requester", style="green")
    table.add_column("Description", style="white")
    table.add_column("Priority", style="yellow")
    table.add_column("Status", style="bold magenta")
    table.add_column("Created At", style="dim")

    for t in tickets:
        table.add_row(
            t.id[:8] + "...",
            t.requester_id,
            t.description[:DESC_TRUNCATE_LIMIT] + ("..." if len(t.description) > DESC_TRUNCATE_LIMIT else ""),
            t.priority.value,
            t.status.value,
            t.created_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


@ticket_app.command("show")
def ticket_show(
    ticket_id: str = typer.Argument(..., help="Full or prefix Ticket ID"),
) -> None:
    """Show details for a specific governance ticket."""
    system = TicketSystem()
    # Support prefix lookup
    all_tickets = system.list_tickets()
    ticket = next((t for t in all_tickets if t.id.startswith(ticket_id)), None)

    if not ticket:
        console.print(f"[bold red]Ticket not found: {ticket_id}[/bold red]")
        raise typer.Exit(code=1)

    details = (
        f"[bold]ID:[/bold] {ticket.id}\n"
        f"[bold]Requester:[/bold] {ticket.requester_id}\n"
        f"[bold]Priority:[/bold] {ticket.priority.value}\n"
        f"[bold]Status:[/bold] {ticket.status.value}\n"
        f"[bold]Created At:[/bold] {ticket.created_at.isoformat()}\n"
        f"[bold]Resolved At:[/bold] {ticket.resolved_at.isoformat() if ticket.resolved_at else '(pending)'}\n"
        f"[bold]Reviewer:[/bold] {ticket.reviewer_id or '(none)'}\n\n"
        f"[bold]Description:[/bold]\n{ticket.description}\n\n"
        f"[bold]Context:[/bold] {ticket.context}"
    )
    console.print(Panel(details, title=f"Ticket: [bold cyan]{ticket.id}[/bold cyan]"))


@ticket_app.command("approve")
def ticket_approve(
    ticket_id: str = typer.Argument(..., help="Ticket ID to approve"),
    reviewer: str = typer.Option("admin", "--reviewer", "-r", help="Reviewer identity"),
) -> None:
    """Approve a pending governance ticket."""
    system = TicketSystem()
    all_tickets = system.list_tickets()
    ticket = next((t for t in all_tickets if t.id.startswith(ticket_id)), None)

    if not ticket:
        console.print(f"[bold red]Ticket not found: {ticket_id}[/bold red]")
        raise typer.Exit(code=1)

    system.resolve_ticket(ticket.id, TicketStatus.APPROVED, reviewer_id=reviewer)
    console.print(f"[bold green]✓ Ticket {ticket.id} approved by {reviewer}.[/bold green]")


@ticket_app.command("reject")
def ticket_reject(
    ticket_id: str = typer.Argument(..., help="Ticket ID to reject"),
    reviewer: str = typer.Option("admin", "--reviewer", "-r", help="Reviewer identity"),
) -> None:
    """Reject a pending governance ticket."""
    system = TicketSystem()
    all_tickets = system.list_tickets()
    ticket = next((t for t in all_tickets if t.id.startswith(ticket_id)), None)

    if not ticket:
        console.print(f"[bold red]Ticket not found: {ticket_id}[/bold red]")
        raise typer.Exit(code=1)

    system.resolve_ticket(ticket.id, TicketStatus.REJECTED, reviewer_id=reviewer)
    console.print(f"[bold red]✗ Ticket {ticket.id} rejected by {reviewer}.[/bold red]")
