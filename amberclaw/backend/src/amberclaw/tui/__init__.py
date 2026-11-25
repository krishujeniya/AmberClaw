"""AmberClaw Terminal User Interface (TUI) Module."""

from amberclaw.tui.app import AmberClawTUIApp
from amberclaw.tui.completion import CommandPalette, SlashCommand
from amberclaw.tui.input import TUIInputHandler, TUIInputResult
from amberclaw.tui.renderer import TUIMessage, TUIRenderer
from amberclaw.tui.status import (
    TUIStatusState,
    render_inspector_card,
    render_status_bar,
)
from amberclaw.tui.themes import (
    DefaultTheme,
    LightTheme,
    OceanTheme,
    TUITheme,
    get_theme,
)

__all__ = [
    "AmberClawTUIApp",
    "CommandPalette",
    "DefaultTheme",
    "LightTheme",
    "OceanTheme",
    "SlashCommand",
    "TUIInputHandler",
    "TUIInputResult",
    "TUIMessage",
    "TUIRenderer",
    "TUIStatusState",
    "TUITheme",
    "get_theme",
    "render_inspector_card",
    "render_status_bar",
]
