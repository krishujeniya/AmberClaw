"""Workspace template installer utility."""

from pathlib import Path
from typing import Any

from loguru import logger
from amberclaw.templates.template import TemplateManager


class TemplateInstaller:
    """Installs rendered template prompt files into a target workspace directory."""

    def __init__(self, template_manager: TemplateManager | None = None):
        self.manager = template_manager or TemplateManager()

    def install_workspace(
        self,
        target_dir: Path | str,
        context: dict[str, Any] | None = None,
        overwrite: bool = False,
    ) -> list[Path]:
        """
        Install template prompt files into target workspace directory.

        Returns list of installed file paths.
        """
        dest_dir = Path(target_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        installed_files = []

        for template_file in TemplateManager.TEMPLATE_FILES:
            target_path = dest_dir / template_file
            if target_path.exists() and not overwrite:
                logger.debug("Skipping existing file {}: overwrite=False", target_path)
                continue

            try:
                rendered_content = self.manager.render_template(template_file, context)
                target_path.write_text(rendered_content, encoding="utf-8")
                installed_files.append(target_path)
                logger.info("Installed template {} to {}", template_file, target_path)
            except Exception as e:
                logger.error("Failed to install template {}: {}", template_file, e)

        return installed_files
