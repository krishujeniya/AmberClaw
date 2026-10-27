"""Workspace prompt template rendering manager for AmberClaw."""

from pathlib import Path
from typing import Any

from loguru import logger


class TemplateManager:
    """Manages workspace markdown prompt templates (AGENTS.md, SOUL.md, TOOLS.md, etc.)."""

    TEMPLATE_FILES = [
        "AGENTS.md",
        "SOUL.md",
        "TOOLS.md",
        "USER.md",
        "HEARTBEAT.md",
    ]

    def __init__(self, template_dir: Path | None = None):
        self.template_dir = template_dir or Path(__file__).parent

    def get_template_path(self, filename: str) -> Path:
        """Get absolute path of a template file."""
        return self.template_dir / filename

    def read_template(self, filename: str) -> str:
        """Read content of a template file."""
        p = self.get_template_path(filename)
        if not p.exists():
            raise FileNotFoundError(f"Template file '{filename}' not found at {p}")
        return p.read_text(encoding="utf-8")

    def render_template(self, filename: str, context: dict[str, Any] | None = None) -> str:
        """Render a template file with context variable substitution."""
        content = self.read_template(filename)
        if not context:
            return content

        rendered = content
        for key, val in context.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", str(val))
            rendered = rendered.replace(f"${{{key}}}", str(val))
        return rendered

    def list_templates(self) -> list[str]:
        """List available template files in template directory."""
        return [f.name for f in self.template_dir.glob("*.md")]
