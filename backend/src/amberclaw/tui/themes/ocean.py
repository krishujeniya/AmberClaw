"""Ocean blue theme for AmberClaw TUI."""

from amberclaw.tui.themes.default import TUITheme

OceanTheme = TUITheme(
    name="ocean",
    primary="bright_cyan",
    secondary="dodger_blue1",
    accent="aquamarine1",
    background="#0b192c",
    surface="#1e3e62",
    text="#eef5ff",
    muted="#8ea7e9",
    success="spring_green1",
    warning="gold1",
    error="deep_pink1",
    user_badge="bold dodger_blue1",
    assistant_badge="bold bright_cyan",
    tool_badge="bold aquamarine1",
)
