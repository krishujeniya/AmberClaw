"""Accessible monochrome / No-Color theme conforming to https://no-color.org standards."""

from amberclaw.tui.themes.default import TUITheme

NoColorTheme = TUITheme(
    name="no-color",
    primary="default",
    secondary="default",
    accent="default",
    background="default",
    text="default",
    muted="dim",
    border="default",
    success="default",
    warning="default",
    danger="bold",
)
