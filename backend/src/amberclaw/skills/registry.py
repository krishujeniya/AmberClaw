"""Central registry for loaded skills."""

from amberclaw.skills.skill import SkillDefinition


class SkillRegistry:
    """Registry maintaining active and disabled skills."""

    def __init__(self) -> None:
        self._skills: dict[str, SkillDefinition] = {}

    def register(self, skill: SkillDefinition) -> None:
        """Register or update a skill definition."""
        self._skills[skill.name] = skill

    def unregister(self, name: str) -> bool:
        """Remove a skill by name."""
        return self._skills.pop(name, None) is not None

    def get(self, name: str) -> SkillDefinition | None:
        """Retrieve a skill definition by name."""
        return self._skills.get(name)

    def list_all(self, enabled_only: bool = True) -> list[SkillDefinition]:
        """List all registered skills."""
        if enabled_only:
            return [s for s in self._skills.values() if s.is_enabled]
        return list(self._skills.values())

    def search(self, query: str) -> list[SkillDefinition]:
        """Search skills by keyword matching on name, description, or tags."""
        q = query.lower()
        results: list[SkillDefinition] = []
        for s in self._skills.values():
            if not s.is_enabled:
                continue
            if (
                q in s.name.lower()
                or q in s.metadata.description.lower()
                or any(q in tag.lower() for tag in s.metadata.tags)
            ):
                results.append(s)
        return results

    def set_enabled(self, name: str, enabled: bool) -> bool:
        """Toggle the enabled state of a registered skill."""
        skill = self._skills.get(name)
        if not skill:
            return False
        skill.metadata.is_enabled = enabled
        return True
