"""Accessible monochrome / No-Color theme conforming to https://no-color.org standards."""

from amberclaw.tui.themes.default import TUITheme

NoColorTheme = TUITheme(
    name="no-color",
    primary="default",
    secondary="default",
    accent="default",
    background="default",
    surface="default",
    text="default",
    muted="dim",
    success="default",
    warning="default",
    error="bold",
    user_badge="bold",
    assistant_badge="bold",
    tool_badge="default",
)
