"""Skill service encapsulating skill discovery, lifecycle registration, and telemetry tracking."""

from pathlib import Path

from loguru import logger

from amberclaw.skills.registry import SkillRegistry
from amberclaw.skills.scanner import SkillScanner
from amberclaw.skills.skill import SkillDefinition
from amberclaw.skills.tracker import SkillUsageMetric, SkillUsageTracker


class SkillService:
    """Service orchestrating skill catalog discovery, state toggling, and execution metrics."""

    def __init__(
        self,
        registry: SkillRegistry | None = None,
        tracker: SkillUsageTracker | None = None,
        scanner: SkillScanner | None = None,
    ) -> None:
        self.registry = registry or SkillRegistry()
        self.tracker = tracker or SkillUsageTracker()
        self.scanner = scanner or SkillScanner()

        # Add default package skills path if it exists
        default_skills_dir = Path(__file__).resolve().parents[1] / "skills"
        if default_skills_dir.exists():
            self.scanner.add_search_path(default_skills_dir)

    def list_skills(self) -> list[SkillDefinition]:
        """Return all currently registered skill definitions."""
        return self.registry.list_all()

    def get_skill(self, name: str) -> SkillDefinition | None:
        """Retrieve a registered skill by unique name."""
        return self.registry.get(name)

    def set_skill_enabled(self, name: str, enabled: bool) -> SkillDefinition | None:
        """Enable or disable a specific registered skill."""
        skill = self.registry.get(name)
        if not skill:
            return None
        self.registry.set_enabled(name, enabled)
        logger.info(
            "Skill '{}' status changed to enabled={}", name, skill.metadata.is_enabled
        )
        return skill

    def discover_and_reload(self) -> list[SkillDefinition]:
        """Scan configured directories and synchronize detected skills into the registry."""
        discovered = self.scanner.scan()
        for s in discovered:
            existing = self.registry.get(s.name)
            if existing and not existing.is_enabled:
                s.metadata.is_enabled = False
            self.registry.register(s)
        logger.info("Discovered and reloaded {} skills", len(discovered))
        return discovered

    def get_metrics(self, name: str) -> SkillUsageMetric | None:
        """Fetch telemetry usage metrics for a specific skill."""
        return self.tracker.get_metric(name)

    def record_usage(
        self,
        name: str,
        duration_ms: float,
        success: bool = True,
    ) -> SkillUsageMetric:
        """Record skill execution metrics."""
        return self.tracker.record_execution(
            skill_name=name,
            duration_ms=duration_ms,
            success=success,
        )
