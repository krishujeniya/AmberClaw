"""Autonomous Skill Self-Improver module."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from loguru import logger

from amberclaw.providers.base import LLMProvider


class SkillImprover:
    """Tracks skill performance telemetry and auto-refines failing skills."""

    SUCCESS_RATE_THRESHOLD = 0.5

    def __init__(self, provider: LLMProvider, workspace: Path):
        self.provider = provider
        self.workspace = workspace
        self.db_path = Path.home() / ".amberclaw" / "skills" / "telemetry.db"
        self.global_skills_dir = Path.home() / ".amberclaw" / "skills" / "auto-created"
        self.workspace_skills_dir = workspace / "skills" / "auto-created"
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the telemetry database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS skill_telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill_name TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    outcome TEXT,
                    error_message TEXT
                )
                """
            )

    def log_execution(self, skill_name: str, outcome: str, error_message: str | None = None) -> None:
        """
        Record a skill execution outcome.

        Args:
            skill_name: Name of the skill.
            outcome: 'success' or 'failure'.
            error_message: Optional error message if failed.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO skill_telemetry (skill_name, outcome, error_message) VALUES (?, ?, ?)",
                (skill_name, outcome, error_message),
            )
        logger.info("SkillImprover: Logged execution for skill '{}': {}", skill_name, outcome)

    def get_success_rate(self, skill_name: str) -> float | None:
        """Calculate success rate for a skill. Returns None if never run."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM skill_telemetry WHERE skill_name = ?",
                (skill_name,),
            )
            total = cursor.fetchone()[0]
            if total == 0:
                return None

            cursor.execute(
                "SELECT COUNT(*) FROM skill_telemetry WHERE skill_name = ? AND outcome = 'success'",
                (skill_name,),
            )
            successes = cursor.fetchone()[0]
            return successes / total

    async def check_and_refine(self, skill_name: str, model: str | None = None) -> bool:
        """
        Check skill performance and auto-refine if success rate falls below 50%.

        Args:
            skill_name: Name of the skill.
            model: Optional model override.

        Returns:
            True if the skill was refined, False otherwise.
        """
        rate = self.get_success_rate(skill_name)
        if rate is None or rate >= self.SUCCESS_RATE_THRESHOLD:
            return False

        logger.info(
            "SkillImprover: Skill '{}' success rate is {:.1f}% (below 50% threshold). Triggering refinement...",
            skill_name,
            rate * 100,
        )

        # Retrieve failure details
        failures = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT error_message, timestamp FROM skill_telemetry WHERE skill_name = ? AND outcome = 'failure' ORDER BY timestamp DESC LIMIT 5",
                (skill_name,),
            )
            failures = cursor.fetchall()

        # Load existing skill content
        skill_content = self._load_skill_content(skill_name)
        if not skill_content:
            logger.warning("SkillImprover: Could not locate skill content for '{}'", skill_name)
            return False

        # Build refinement prompt
        failure_log_str = "\n".join(
            f"- [{row[1]}] Error: {row[0]}" for row in failures if row[0]
        )

        prompt = (
            "You are an expert systems debugger and software architect.\n"
            f"The following autonomous agent skill has a failure rate of {int((1 - rate) * 100)}%.\n\n"
            f"Skill Content:\n{skill_content}\n\n"
            f"Recent Failure Logs:\n{failure_log_str}\n\n"
            "Analyze the failure logs and refine the skill document to prevent these failures.\n"
            "Add explicit instructions, better error handling hints, prerequisite checks, or corrected command arguments.\n"
            "Ensure the YAML frontmatter remains intact.\n"
            "Respond ONLY with the final refined Markdown document content. Do not add any conversational text before or after."
        )

        try:
            response = await self.provider.chat_with_retry(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                temperature=0.2,
            )

            refined_content = response.content or ""
            if not refined_content.strip():
                return False

            # Clean markdown code blocks wrappers
            if refined_content.strip().startswith("```markdown"):
                refined_content = refined_content.strip().replace("```markdown", "", 1).rstrip("`").strip()
            elif refined_content.strip().startswith("```"):
                refined_content = refined_content.strip().replace("```", "", 1).rstrip("`").strip()

            # Save refined skill back
            self._save_skill_content(skill_name, refined_content)
            logger.info("SkillImprover: Successfully refined skill '{}'", skill_name)
            return True

        except Exception as e:
            logger.error("SkillImprover: Failed to refine skill '{}': {}", skill_name, e)
            return False

    def _load_skill_content(self, skill_name: str) -> str | None:
        """Load content from global or workspace files."""
        global_path = self.global_skills_dir / f"{skill_name}.md"
        if global_path.exists():
            return global_path.read_text(encoding="utf-8")

        workspace_path = self.workspace_skills_dir / skill_name / "SKILL.md"
        if workspace_path.exists():
            return workspace_path.read_text(encoding="utf-8")

        return None

    def _save_skill_content(self, skill_name: str, content: str) -> None:
        """Save updated skill content to both global and workspace paths if they exist."""
        global_path = self.global_skills_dir / f"{skill_name}.md"
        if global_path.exists():
            global_path.write_text(content, encoding="utf-8")

        workspace_path = self.workspace_skills_dir / skill_name / "SKILL.md"
        if workspace_path.exists():
            workspace_path.write_text(content, encoding="utf-8")
