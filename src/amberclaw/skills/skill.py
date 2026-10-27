"""Core skill metadata and definition data structures."""

from pathlib import Path

from pydantic import BaseModel, Field


class SkillMetadata(BaseModel):
    """Metadata describing a single AmberClaw skill."""

    name: str = Field(..., description="Unique skill name identifier.")
    version: str = Field(default="1.0.0", description="Semver skill version.")
    description: str = Field(default="", description="Detailed human-readable description of capabilities.")
    author: str | None = Field(default=None, description="Author or organization name.")
    tags: list[str] = Field(default_factory=list, description="Descriptive search tags.")
    dependencies: list[str] = Field(default_factory=list, description="Required runtime dependencies or packages.")
    entrypoint: str | None = Field(default=None, description="Path to execution script or module.")
    is_enabled: bool = Field(default=True, description="Whether skill is active and discoverable.")


class SkillDefinition(BaseModel):
    """Full skill bundle including metadata, instructions, and file locations."""

    metadata: SkillMetadata
    instructions: str = Field(default="", description="Instructions or prompt content for LLM.")
    directory_path: Path | None = Field(default=None, description="Local path to skill directory.")

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def is_enabled(self) -> bool:
        return self.metadata.is_enabled
