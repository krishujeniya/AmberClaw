"""Filesystem scanner for discovering available skills across directories."""

from pathlib import Path

from amberclaw.skills.loader import SkillLoader
from amberclaw.skills.skill import SkillDefinition


class SkillScanner:
    """Recursively or shallowly scans directories to discover skill definitions."""

    def __init__(self, search_paths: list[Path | str] | None = None) -> None:
        self.search_paths = [Path(p) for p in (search_paths or [])]
        self.loader = SkillLoader()

    def add_search_path(self, path: Path | str) -> None:
        """Add a path to the skill discovery scanner."""
        p = Path(path)
        if p not in self.search_paths:
            self.search_paths.append(p)

    def scan(self) -> list[SkillDefinition]:
        """Scan all registered search paths and discover valid skills."""
        discovered: dict[str, SkillDefinition] = {}

        for base_path in self.search_paths:
            if not base_path.exists() or not base_path.is_dir():
                continue

            # First, check if base_path itself is a skill
            direct_skill = self.loader.load_from_directory(base_path)
            if direct_skill:
                discovered[direct_skill.name] = direct_skill

            # Next, inspect each child directory
            for child in base_path.iterdir():
                if child.is_dir():
                    skill = self.loader.load_from_directory(child)
                    if skill and skill.name not in discovered:
                        discovered[skill.name] = skill

        return list(discovered.values())
