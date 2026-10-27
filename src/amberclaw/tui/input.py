"""Input buffer and interaction handling for AmberClaw TUI."""

from pydantic import BaseModel, Field

from amberclaw.tui.completion import CommandPalette


class TUIInputResult(BaseModel):
    """Result of parsing a user input line."""

    type: str  # "command", "chat", "empty"
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    raw_text: str = ""


class TUIInputHandler:
    """Manages command history, multiline buffering, and input parsing."""

    def __init__(self, max_history: int = 100) -> None:
        self.history: list[str] = []
        self.max_history = max_history
        self.palette = CommandPalette()

    def add_to_history(self, text: str) -> None:
        """Append non-empty input to command history."""
        cleaned = text.strip()
        if cleaned and (not self.history or self.history[-1] != cleaned):
            self.history.append(cleaned)
            if len(self.history) > self.max_history:
                self.history.pop(0)

    def process_input(self, raw_text: str) -> TUIInputResult:
        """Parse raw terminal input into a command or chat message."""
        cleaned = raw_text.strip()
        if not cleaned:
            return TUIInputResult(type="empty", raw_text=raw_text)

        self.add_to_history(cleaned)

        parsed = self.palette.parse_command(cleaned)
        if parsed is not None:
            cmd_name, args = parsed
            return TUIInputResult(
                type="command",
                command=cmd_name,
                args=args,
                raw_text=cleaned,
            )

        return TUIInputResult(
            type="chat",
            raw_text=cleaned,
        )
