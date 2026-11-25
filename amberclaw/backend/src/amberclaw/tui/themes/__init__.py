"""Theme registry for AmberClaw TUI."""

from __future__ import annotations

import os

from amberclaw.tui.themes.default import DefaultTheme, TUITheme
from amberclaw.tui.themes.light import LightTheme
from amberclaw.tui.themes.no_color import NoColorTheme
from amberclaw.tui.themes.ocean import OceanTheme

THEMES: dict[str, TUITheme] = {
    "default": DefaultTheme,
    "dark": DefaultTheme,
    "light": LightTheme,
    "ocean": OceanTheme,
    "no-color": NoColorTheme,
    "monochrome": NoColorTheme,
}


def get_theme(name: str = "default") -> TUITheme:
    """Retrieve theme by name, automatically honoring NO_COLOR environment variable."""
    if os.getenv("NO_COLOR"):
        return NoColorTheme
    return THEMES.get(name.lower(), DefaultTheme)


__all__ = [
    "THEMES",
    "DefaultTheme",
    "LightTheme",
    "NoColorTheme",
    "OceanTheme",
    "TUITheme",
    "get_theme",
]
