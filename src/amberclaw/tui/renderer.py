"""Message and tool execution timeline renderer for AmberClaw TUI."""

import datetime
from typing import Any

from pydantic import BaseModel, Field
from rich.console import Group, RenderableType
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from amberclaw.tui.themes.default import DefaultTheme, TUITheme


class TUIMessage(BaseModel):
    """A single renderable message or tool interaction event."""

    role: str = "assistant"
    content: str = ""
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    tool_output: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC).strftime("%H:%M:%S"))
    is_thought: bool = False
    is_approval_request: bool = False
    approval_ticket_id: str | None = None


class TUIRenderer:
    """Renders formatted messages, Markdown text, tool call cards, and approval widgets."""

    def __init__(self, theme: TUITheme = DefaultTheme) -> None:
        self.theme = theme

    def render_message(self, msg: TUIMessage) -> RenderableType:
        """Render a single message item according to its role and content type."""
        if msg.is_thought:
            thought_text = Text(msg.content, style="italic grey70")
            return Panel(
                thought_text,
                title=f"💭 [dim]Thought ({msg.timestamp})[/dim]",
                border_style="dim white",
                padding=(0, 1),
            )

        if msg.role == "tool" or msg.tool_name:
            title = f"🛠️ Tool: [bold]{msg.tool_name or 'tool'}[/bold] ({msg.timestamp})"
            items: list[RenderableType] = []

            if msg.tool_args:
                args_str = str(msg.tool_args)
                items.append(Text("Arguments: ", style="bold") + Text(args_str, style="cyan"))

            if msg.tool_output:
                out_str = msg.tool_output.strip()
                if out_str.startswith("{") or out_str.startswith("["):
                    items.append(Syntax(out_str, "json", theme="monokai", word_wrap=True))
                else:
                    items.append(Text(out_str, style=self.theme.text))

            if not items and msg.content:
                items.append(Text(msg.content, style=self.theme.text))

            return Panel(
                Group(*items),
                title=title,
                border_style=self.theme.tool_badge,
                padding=(0, 1),
            )

        if msg.is_approval_request:
            return self.render_approval_prompt(
                ticket_id=msg.approval_ticket_id or "TICKET",
                action=msg.tool_name or "Privileged Execution",
                details=msg.content,
            )

        if msg.role == "user":
            header = Text(f"🧑 User ({msg.timestamp})", style=self.theme.user_badge)
            body = Text(msg.content, style=self.theme.text)
            return Panel(
                body,
                title=header.markup,
                border_style="cyan",
                padding=(0, 1),
            )

        header = Text(f"🐾 AmberClaw ({msg.timestamp})", style=self.theme.assistant_badge)
        try:
            body = Markdown(msg.content)
        except Exception:
            body = Text(msg.content, style=self.theme.text)

        return Panel(
            body,
            title=header.markup,
            border_style=self.theme.primary,
            padding=(0, 1),
        )

    def render_approval_prompt(
        self,
        ticket_id: str,
        action: str,
        details: str,
    ) -> Panel:
        """Render a high-visibility human-in-the-loop approval card."""
        text = Text()
        text.append(f"Action: {action}\n", style="bold yellow")
        text.append(f"Details: {details}\n\n", style="white")
        text.append(f"To respond, type: /approve {ticket_id}  or  /reject {ticket_id}", style="bold green")

        return Panel(
            text,
            title=f"⚠️ [bold red]Human-in-the-Loop Approval Required [{ticket_id}][/bold red]",
            border_style="red",
            padding=(1, 2),
        )

    def render_timeline(self, messages: list[TUIMessage]) -> Group:
        """Render a full list of messages into a single timeline renderable."""
        if not messages:
            empty_text = Text("No messages in session yet. Type a message or /help to start.", style=self.theme.muted)
            return Group(Panel(empty_text, border_style="dim"))

        rendered = [self.render_message(m) for m in messages]
        return Group(*rendered)
