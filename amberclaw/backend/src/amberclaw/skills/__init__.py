"""AmberClaw skills management, discovery, and registry module."""

from pydantic import BaseModel, Field

from amberclaw.skills.format import parse_skill_markdown, serialize_skill_markdown
from amberclaw.skills.hub import ClawHubClient, HubSkillPackage
from amberclaw.skills.loader import SkillLoader
from amberclaw.skills.registry import SkillRegistry
from amberclaw.skills.scanner import SkillScanner
from amberclaw.skills.skill import SkillDefinition, SkillMetadata
from amberclaw.skills.tracker import SkillUsageMetric, SkillUsageTracker


class SkillsModuleConfig(BaseModel):
    """Configuration for the amberclaw.skills module."""

    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = [
    "ClawHubClient",
    "HubSkillPackage",
    "SkillDefinition",
    "SkillLoader",
    "SkillMetadata",
    "SkillRegistry",
    "SkillScanner",
    "SkillUsageMetric",
    "SkillUsageTracker",
    "SkillsModuleConfig",
    "parse_skill_markdown",
    "serialize_skill_markdown",
]
