"""Status and metrics bar renderer for AmberClaw TUI."""

from pydantic import BaseModel, Field
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from amberclaw.tui.themes.default import DefaultTheme, TUITheme


class TUIStatusState(BaseModel):
    """Real-time runtime state for TUI display."""

    model: str = "gpt-4o"
    session_id: str = "cli:direct"
    provider: str = "litellm"
    workspace: str = "./workspace"
    total_tokens: int = Field(default=0, ge=0)
    active_sandbox: str = "local"
    pending_approvals: int = Field(default=0, ge=0)
    is_streaming: bool = False
    latency_ms: float = 0.0


def render_status_bar(
    state: TUIStatusState,
    theme: TUITheme = DefaultTheme,
) -> Panel:
    """Render the top status bar displaying runtime and session details."""
    table = Table.grid(expand=True)
    table.add_column(justify="left", ratio=3)
    table.add_column(justify="center", ratio=3)
    table.add_column(justify="right", ratio=3)

    left = Text()
    left.append(" 🐾 AmberClaw AI OS ", style=theme.user_badge)
    left.append(f"│ Session: {state.session_id} ", style=theme.muted)
    left.append(f"│ Sandbox: [{state.active_sandbox}]", style=theme.accent)

    center = Text()
    center.append(f"Model: {state.model} ", style=theme.assistant_badge)
    center.append(f"({state.provider})", style=theme.muted)
    if state.is_streaming:
        center.append(" ⚡ [Streaming]", style=theme.warning)

    right = Text()
    right.append(f"Tokens: {state.total_tokens} ", style=theme.text)
    if state.latency_ms > 0:
        right.append(f"({state.latency_ms:.0f}ms) ", style=theme.muted)
    if state.pending_approvals > 0:
        right.append(f"│ ⚠️ {state.pending_approvals} Approval(s)", style=theme.error)
    else:
        right.append("│ Ready", style=theme.success)

    table.add_row(left, center, right)
    return Panel(table, style=theme.text, border_style=theme.primary, padding=(0, 1))


def render_inspector_card(
    state: TUIStatusState,
    theme: TUITheme = DefaultTheme,
) -> Panel:
    """Render the right-hand inspection card for active execution metrics."""
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style=theme.muted, width=14)
    table.add_column(style=theme.text)

    table.add_row("Model", state.model)
    table.add_row("Provider", state.provider)
    table.add_row("Sandbox", state.active_sandbox)
    table.add_row("Workspace", state.workspace)
    table.add_row("Tokens", str(state.total_tokens))
    table.add_row("Approvals", f"[red]{state.pending_approvals}[/red]" if state.pending_approvals > 0 else "[green]0[/green]")
    table.add_row("Status", "[yellow]Streaming...[/yellow]" if state.is_streaming else "[green]Idle[/green]")

    return Panel(table, title="🔍 [bold]Runtime Inspector[/bold]", border_style=theme.secondary)
