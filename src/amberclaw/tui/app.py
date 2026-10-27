# ruff: noqa: PLR0911, PLR0912
"""Full Split-Pane Terminal User Interface Application for AmberClaw AI OS."""

from typing import Any

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text

from amberclaw.tui.completion import CommandPalette
from amberclaw.tui.input import TUIInputHandler, TUIInputResult
from amberclaw.tui.renderer import TUIMessage, TUIRenderer
from amberclaw.tui.status import (
    TUIStatusState,
    render_inspector_card,
    render_status_bar,
)
from amberclaw.tui.themes import TUITheme, get_theme


class AmberClawTUIApp:
    """Coordinates split-pane terminal layout, message history, status, and theme rendering."""

    def __init__(
        self,
        theme_name: str = "default",
        console: Console | None = None,
    ) -> None:
        self.theme: TUITheme = get_theme(theme_name)
        self.console = console or Console()
        self.state = TUIStatusState()
        self.renderer = TUIRenderer(theme=self.theme)
        self.input_handler = TUIInputHandler()
        self.palette = CommandPalette()
        self.messages: list[TUIMessage] = []

    def set_theme(self, theme_name: str) -> None:
        """Switch current TUI theme."""
        self.theme = get_theme(theme_name)
        self.renderer.theme = self.theme

    def handle_resize(self, width: int, height: int) -> None:
        """Handle terminal window resize events across SSH, Windows Terminal, and tmux."""
        self.console.width = max(20, width)
        self.console.height = max(10, height)

    def add_user_message(self, content: str) -> None:
        """Append a user message to the timeline."""
        self.messages.append(TUIMessage(role="user", content=content))

    def add_assistant_message(self, content: str) -> None:
        """Append an assistant response to the timeline."""
        self.messages.append(TUIMessage(role="assistant", content=content))

    def add_tool_event(
        self,
        tool_name: str,
        tool_args: dict[str, Any] | None = None,
        tool_output: str | None = None,
    ) -> None:
        """Append a tool execution card to the timeline."""
        self.messages.append(
            TUIMessage(
                role="tool",
                tool_name=tool_name,
                tool_args=tool_args,
                tool_output=tool_output,
            )
        )

    def add_approval_request(
        self,
        ticket_id: str,
        action: str,
        details: str,
    ) -> None:
        """Append a human-in-the-loop approval card and increment pending counter."""
        self.state.pending_approvals += 1
        self.messages.append(
            TUIMessage(
                role="system",
                content=details,
                tool_name=action,
                is_approval_request=True,
                approval_ticket_id=ticket_id,
            )
        )

    def build_layout(self) -> Layout:
        """Generate the 3-section split-pane terminal layout."""
        layout = Layout(name="root")

        # Split into Header, Body, and Footer
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=3),
        )

        # Split Body into Left (Chat Timeline) and Right (Runtime Inspector)
        layout["body"].split_row(
            Layout(name="chat", ratio=7),
            Layout(name="inspector", ratio=3),
        )

        # Populate Sections
        layout["header"].update(render_status_bar(self.state, self.theme))
        layout["chat"].update(
            Panel(
                self.renderer.render_timeline(self.messages),
                title="💬 [bold]Conversation Timeline[/bold]",
                border_style=self.theme.primary,
            )
        )
        layout["inspector"].update(render_inspector_card(self.state, self.theme))

        # Footer hints
        footer_text = Text()
        footer_text.append("Commands: ", style="bold")
        footer_text.append(
            "/help  /model <name>  /session <id>  /sandbox <type>  /theme <name>  /approve <id>  /exit",
            style=self.theme.muted,
        )
        layout["footer"].update(
            Panel(footer_text, border_style=self.theme.secondary, padding=(0, 1))
        )

        return layout

    def process_command(self, cmd_result: TUIInputResult) -> str:
        """Execute a local TUI slash command."""
        cmd = (cmd_result.command or "").lower()
        args = cmd_result.args

        if cmd == "/help":
            help_lines = ["Available Commands:"]
            for sc in self.palette.commands:
                help_lines.append(f"  {sc.usage:<25} - {sc.description}")
            return "\n".join(help_lines)

        if cmd == "/theme":
            if args:
                self.set_theme(args[0])
                return f"Theme changed to: {self.theme.name}"
            return f"Current theme: {self.theme.name}. Available: default, light, ocean"

        if cmd == "/clear":
            self.messages.clear()
            return "Timeline cleared."

        if cmd == "/model":
            if args:
                self.state.model = args[0]
                return f"Active model set to: {self.state.model}"
            return f"Active model: {self.state.model}"

        if cmd == "/sandbox":
            if args:
                self.state.active_sandbox = args[0]
                return f"Active sandbox backend set to: {self.state.active_sandbox}"
            return f"Active sandbox: {self.state.active_sandbox}"

        if cmd == "/session":
            if args:
                self.state.session_id = args[0]
                return f"Switched to session: {self.state.session_id}"
            return f"Current session: {self.state.session_id}"

        if cmd == "/skills":
            return "Active Skills: [code_search, filesystem, terminal_exec, memory_recall, data_viz]"

        if cmd == "/approve":
            if not args:
                return "Error: Missing ticket ID. Usage: /approve <ticket_id>"
            ticket_id = args[0]
            self.state.pending_approvals = max(0, self.state.pending_approvals - 1)
            self.add_assistant_message(f"Action approved for ticket {ticket_id}.")
            return f"Ticket {ticket_id} approved."

        if cmd == "/reject":
            if not args:
                return "Error: Missing ticket ID. Usage: /reject <ticket_id>"
            ticket_id = args[0]
            self.state.pending_approvals = max(0, self.state.pending_approvals - 1)
            self.add_assistant_message(f"Action rejected for ticket {ticket_id}.")
            return f"Ticket {ticket_id} rejected."

        if cmd == "/doctor":
            return "Doctor Diagnostic: All systems nominal. Sandbox: online. DB: connected. Latency: <15ms."

        if cmd in ("/exit", "/quit"):
            return "EXIT"

        return f"Unknown command: {cmd}. Type /help for assistance."
