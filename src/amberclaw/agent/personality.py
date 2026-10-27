"""Agent personality profiling, stylistic tone, and behavioral conditioning."""

from typing import Literal

from pydantic import BaseModel, Field


class PersonalityProfile(BaseModel):
    """Configures the agent's tone, verbosity, and behavioral persona."""

    name: str = Field(default="AmberClaw", description="Agent public persona name.")
    tone: Literal["concise", "enthusiastic", "technical", "formal", "casual"] = Field(
        default="concise", description="Communication tone."
    )
    verbosity: Literal["minimal", "standard", "detailed"] = Field(
        default="standard", description="Response length and verbosity level."
    )
    technical_depth: int = Field(
        default=3, ge=1, le=5, description="Technical depth scale from 1 (simple) to 5 (expert)."
    )
    empathy: bool = Field(default=True, description="Enable empathetic acknowledgments.")
    custom_directives: list[str] = Field(
        default_factory=list, description="Explicit personal preferences or persona instructions."
    )

    def render_system_prompt_directive(self) -> str:
        """Render persona directives to be prepended to the system prompt."""
        directives = [
            f"You are {self.name}.",
            f"Communication Tone: {self.tone.capitalize()}.",
            f"Verbosity: {self.verbosity.capitalize()}.",
            f"Technical Depth: Level {self.technical_depth} of 5.",
        ]

        if self.tone == "concise":
            directives.append("Prioritize brevity and high signal-to-noise ratio. Avoid fluff.")
        elif self.tone == "technical":
            directives.append("Include precise code references, API signatures, and architectural rationale.")

        for d in self.custom_directives:
            directives.append(f"- {d}")

        return "\n".join(directives)
