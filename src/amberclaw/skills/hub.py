"""Client interface for interacting with the ClawHub skill registry."""

from pathlib import Path

from pydantic import BaseModel, Field

from amberclaw.skills.format import serialize_skill_markdown
from amberclaw.skills.skill import SkillDefinition, SkillMetadata


class HubSkillPackage(BaseModel):
    """A remote or local distributable skill package."""

    name: str
    version: str
    description: str
    author: str | None = None
    tags: list[str] = Field(default_factory=list)
    instructions: str = Field(default="")
    download_url: str | None = None


class ClawHubClient:
    """Interface for discovering, installing, and publishing skills to/from ClawHub."""

    def __init__(self, local_skills_dir: Path | str | None = None) -> None:
        self.local_skills_dir = Path(local_skills_dir) if local_skills_dir else Path("./skills")

    def install_skill(
        self,
        package: HubSkillPackage,
        target_dir: Path | str | None = None,
    ) -> Path:
        """Install a skill package locally as a SKILL.md directory bundle."""
        dest_base = Path(target_dir) if target_dir else self.local_skills_dir
        dest_dir = dest_base / package.name
        dest_dir.mkdir(parents=True, exist_ok=True)

        meta = SkillMetadata(
            name=package.name,
            version=package.version,
            description=package.description,
            author=package.author,
            tags=package.tags,
        )

        skill_md_content = serialize_skill_markdown(meta, package.instructions)
        skill_file = dest_dir / "SKILL.md"
        skill_file.write_text(skill_md_content, encoding="utf-8")

        return dest_dir

    def package_skill(self, skill: SkillDefinition) -> HubSkillPackage:
        """Convert a local SkillDefinition into a publishable HubSkillPackage."""
        return HubSkillPackage(
            name=skill.name,
            version=skill.metadata.version,
            description=skill.metadata.description,
            author=skill.metadata.author,
            tags=skill.metadata.tags,
            instructions=skill.instructions,
        )
