"""Template persona marketplace directory."""

from pydantic import BaseModel


class PersonaTemplate(BaseModel):
    id: str
    name: str
    description: str
    tags: list[str] = []
    author: str = "AmberClaw"


class TemplateMarket:
    """Catalog of built-in and community agent persona templates."""

    BUILTIN_PERSONAS = [
        PersonaTemplate(
            id="default-agent",
            name="Default OS Assistant",
            description="General-purpose zero-trust AI assistant persona",
            tags=["general", "default"],
        ),
        PersonaTemplate(
            id="code-auditor",
            name="Security & Code Auditor",
            description="Specialized persona for code security analysis and refactoring",
            tags=["security", "coding"],
        ),
        PersonaTemplate(
            id="data-scientist",
            name="Data Science Assistant",
            description="Persona tailored for data cleaning, EDA, visualization, and ML modeling",
            tags=["data", "analytics"],
        ),
    ]

    def __init__(self):
        self._personas = {p.id: p for p in self.BUILTIN_PERSONAS}

    def list_personas(self) -> list[PersonaTemplate]:
        """List all registered persona templates."""
        return list(self._personas.values())

    def get_persona(self, persona_id: str) -> PersonaTemplate | None:
        """Get a persona template by ID."""
        return self._personas.get(persona_id)

    def register_persona(self, persona: PersonaTemplate) -> None:
        """Register a new persona template."""
        self._personas[persona.id] = persona
