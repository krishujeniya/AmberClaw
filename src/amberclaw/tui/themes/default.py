"""Default dark theme for AmberClaw TUI."""

from pydantic import BaseModel, Field


class TUITheme(BaseModel):
    """Color palette and styling tokens for the AmberClaw TUI."""

    name: str = "default"
    primary: str = Field(default="deep_orange", description="Primary accent color")
    secondary: str = Field(default="amber", description="Secondary accent color")
    accent: str = Field(default="gold1", description="Highlight accent color")
    background: str = Field(default="#121214", description="Terminal background")
    surface: str = Field(default="#1e1e24", description="Card/Panel surface")
    text: str = Field(default="white", description="Primary body text")
    muted: str = Field(default="grey70", description="Muted/secondary text")
    success: str = Field(default="green3", description="Success indicator")
    warning: str = Field(default="yellow3", description="Warning indicator")
    error: str = Field(default="red3", description="Error indicator")
    user_badge: str = Field(default="bold bright_cyan", description="User message badge")
    assistant_badge: str = Field(default="bold deep_orange", description="Assistant message badge")
    tool_badge: str = Field(default="bold gold1", description="Tool execution badge")


DefaultTheme = TUITheme(
    name="default",
    primary="bright_yellow",
    secondary="bright_cyan",
    accent="gold1",
    background="#121214",
    surface="#1e1e24",
    text="white",
    muted="grey70",
    success="green",
    warning="yellow",
    error="red",
    user_badge="bold cyan",
    assistant_badge="bold yellow",
    tool_badge="bold magenta",
)
