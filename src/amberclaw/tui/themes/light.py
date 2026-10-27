"""Light high-contrast theme for AmberClaw TUI."""

from amberclaw.tui.themes.default import TUITheme

LightTheme = TUITheme(
    name="light",
    primary="blue",
    secondary="dark_cyan",
    accent="dark_goldenrod",
    background="#ffffff",
    surface="#f0f2f5",
    text="black",
    muted="grey30",
    success="dark_green",
    warning="dark_orange",
    error="dark_red",
    user_badge="bold blue",
    assistant_badge="bold dark_cyan",
    tool_badge="bold purple",
)
