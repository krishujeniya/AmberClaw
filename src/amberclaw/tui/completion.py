"""Command palette and autocompletion helper for AmberClaw TUI."""

from dataclasses import dataclass, field


@dataclass
class SlashCommand:
    """Definition of an interactive TUI slash command."""

    name: str
    description: str
    usage: str = ""
    aliases: list[str] = field(default_factory=list)


SLASH_COMMANDS: list[SlashCommand] = [
    SlashCommand(name="/help", description="Show available slash commands and usage", usage="/help"),
    SlashCommand(name="/session", description="Switch or create conversation session", usage="/session <session_id>"),
    SlashCommand(name="/model", description="Switch active LLM model", usage="/model <model_name>"),
    SlashCommand(name="/sandbox", description="Switch active execution sandbox backend", usage="/sandbox <backend>"),
    SlashCommand(name="/theme", description="Switch TUI color theme (default, light, ocean)", usage="/theme <name>"),
    SlashCommand(name="/skills", description="List loaded agent skills and tools", usage="/skills"),
    SlashCommand(name="/approve", description="Approve a pending human-in-the-loop ticket", usage="/approve <ticket_id>"),
    SlashCommand(name="/reject", description="Reject a pending human-in-the-loop ticket", usage="/reject <ticket_id>"),
    SlashCommand(name="/doctor", description="Run system diagnostic checks", usage="/doctor"),
    SlashCommand(name="/clear", description="Clear current conversation timeline", usage="/clear"),
    SlashCommand(name="/exit", description="Exit AmberClaw TUI", usage="/exit", aliases=["/quit"]),
]


class CommandPalette:
    """Autocomplete and command dispatcher for slash commands."""

    def __init__(self, commands: list[SlashCommand] | None = None) -> None:
        self.commands = commands or SLASH_COMMANDS

    def suggest(self, prefix: str) -> list[SlashCommand]:
        """Suggest matching slash commands for a given prefix."""
        if not prefix.startswith("/"):
            return []

        clean_prefix = prefix.strip().lower()
        matches: list[SlashCommand] = []

        for cmd in self.commands:
            if cmd.name.startswith(clean_prefix) or any(alias.startswith(clean_prefix) for alias in cmd.aliases):
                matches.append(cmd)

        return matches

    def parse_command(self, text: str) -> tuple[str, list[str]] | None:
        """Parse raw input into command name and arguments if it is a slash command."""
        trimmed = text.strip()
        if not trimmed.startswith("/"):
            return None

        parts = trimmed.split()
        cmd_name = parts[0].lower()
        args = parts[1:]

        # Check aliases
        for cmd in self.commands:
            if cmd.name == cmd_name or cmd_name in cmd.aliases:
                return (cmd.name, args)

        return (cmd_name, args)
