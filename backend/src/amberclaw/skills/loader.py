"""Loads skill bundles from local directories and files."""

import json
from pathlib import Path

from loguru import logger

from amberclaw.skills.format import parse_skill_markdown
from amberclaw.skills.skill import SkillDefinition, SkillMetadata


class SkillLoader:
    """Loads SkillDefinition instances from filesystem directories."""

    def load_from_directory(self, skill_dir: Path | str) -> SkillDefinition | None:
        """Load a skill definition from a skill directory."""
        dir_path = Path(skill_dir)
        if not dir_path.is_dir():
            return None

        # Check for SKILL.md
        skill_md = dir_path / "SKILL.md"
        if skill_md.exists():
            content = skill_md.read_text(encoding="utf-8")
            meta, instructions = parse_skill_markdown(content)
            # If name is default, fallback to directory name
            if meta.name == "unnamed_skill":
                meta.name = dir_path.name
            return SkillDefinition(
                metadata=meta,
                instructions=instructions,
                directory_path=dir_path,
            )

        # Check for skill.json
        skill_json = dir_path / "skill.json"
        if skill_json.exists():
            try:
                data = json.loads(skill_json.read_text(encoding="utf-8"))
                meta = SkillMetadata(**data)
                instructions = ""
                instructions_file = dir_path / "instructions.md"
                if instructions_file.exists():
                    instructions = instructions_file.read_text(encoding="utf-8")
                return SkillDefinition(
                    metadata=meta,
                    instructions=instructions,
                    directory_path=dir_path,
                )
            except Exception as e:
                logger.debug(f"Failed to load skill.json from {dir_path}: {e}")

        # Fallback: treat directory with any .md file as skill
        md_files = list(dir_path.glob("*.md"))
        if md_files:
            content = md_files[0].read_text(encoding="utf-8")
            meta, instructions = parse_skill_markdown(content)
            if meta.name == "unnamed_skill":
                meta.name = dir_path.name
            return SkillDefinition(
                metadata=meta,
                instructions=instructions,
                directory_path=dir_path,
            )

        return None
