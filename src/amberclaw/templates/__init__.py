"""Workspace templates package for AmberClaw."""

from amberclaw.templates.installer import TemplateInstaller
from amberclaw.templates.market import PersonaTemplate, TemplateMarket
from amberclaw.templates.scrubber import TemplateScrubber
from amberclaw.templates.template import TemplateManager

__all__ = [
    "TemplateManager",
    "TemplateInstaller",
    "TemplateScrubber",
    "TemplateMarket",
    "PersonaTemplate",
]
