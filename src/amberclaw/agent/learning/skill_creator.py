"""Autonomous Skill Creator module."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from loguru import logger

from amberclaw.providers.base import LLMProvider


class SkillCreator:
    """Monitors agent trajectories and autonomously synthesizes reusable skills."""

    def __init__(self, provider: LLMProvider, workspace: Path):
        self.provider = provider
        self.workspace = workspace
        self.global_skills_dir = Path.home() / ".amberclaw" / "skills" / "auto-created"
        self.workspace_skills_dir = workspace / "skills" / "auto-created"

    # Thresholds constants
    TURNS_THRESHOLD = 3
    TOOL_CALLS_THRESHOLD = 5

    async def monitor_and_create(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
    ) -> Path | None:
        """
        Evaluate conversation trajectory. If it exceeds limits, synthesize a skill.

        Args:
            messages: List of message dictionaries in the trajectory.
            model: Optional model override.

        Returns:
            Path to the saved skill file, or None if no skill was created.
        """
        # Count turns and tool calls
        assistant_turns = 0
        tool_calls_count = 0

        for msg in messages:
            role = msg.get("role")
            if role == "assistant":
                assistant_turns += 1
                tcs = msg.get("tool_calls")
                if tcs:
                    tool_calls_count += len(tcs)

        logger.debug(
            "SkillCreator: Trajectory has {} assistant turns and {} tool calls",
            assistant_turns,
            tool_calls_count,
        )

        # Thresholds check
        if assistant_turns <= self.TURNS_THRESHOLD and tool_calls_count <= self.TOOL_CALLS_THRESHOLD:
            return None

        logger.info(
            "SkillCreator: Threshold met (turns={} > 3 or tool_calls={} > 5). Synthesizing skill...",
            assistant_turns,
            tool_calls_count,
        )

        # Build trajectory string
        trajectory_str = ""
        for i, msg in enumerate(messages):
            role = msg.get("role")
            content = msg.get("content") or ""
            tcs = msg.get("tool_calls")

            # Clean thinking blocks
            if "<think>" in content:
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

            trajectory_str += f"\n[{i}] {role.upper()}: {content[:1000]}"
            if tcs:
                trajectory_str += f"\n    (Tool Calls: {tcs})"

        from amberclaw.security.secret_scanner import SecretScanner
        trajectory_str = SecretScanner.redact_text(trajectory_str)

        prompt = (
            "You are an expert systems engineer and software architect.\n"
            "Analyze this execution trajectory of an AI agent trying to solve a complex user task. "
            "Identify the core reusable task, recipe, or workflow that the agent successfully performed, "
            "and synthesize a clean, structured Markdown skill document.\n\n"
            f"Trajectory:\n{trajectory_str}\n\n"
            "Format the skill document with standard YAML frontmatter exactly as follows:\n"
            "```markdown\n"
            "---\n"
            "name: skill-name-kebab-case\n"
            "description: Brief explanation of what this skill does.\n"
            "---\n"
            "# Skill: [Human Readable Name]\n\n"
            "## Steps\n"
            "1. Step 1...\n"
            "2. Step 2...\n\n"
            "## Known Facts / Constraints\n"
            "- Constraint 1...\n\n"
            "## Verification\n"
            "Explain how to verify if this skill has successfully run.\n"
            "```\n\n"
            "Respond ONLY with the final Markdown document content. Do not add any conversational text before or after."
        )

        try:
            response = await self.provider.chat_with_retry(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                temperature=0.2,
            )

            content = response.content or ""
            if not content.strip():
                return None

            # Clean markdown code blocks wrappers if the model returned them
            if content.strip().startswith("```markdown"):
                content = content.strip().replace("```markdown", "", 1).rstrip("`").strip()
            elif content.strip().startswith("```"):
                content = content.strip().replace("```", "", 1).rstrip("`").strip()

            # Parse the name from frontmatter
            name_match = re.search(r"name:\s*([a-zA-Z0-9_-]+)", content)
            skill_name = name_match.group(1).strip() if name_match else "unnamed-skill"

            # 1. Save to ~/.amberclaw/skills/auto-created/[skill].md
            self.global_skills_dir.mkdir(parents=True, exist_ok=True)
            global_path = self.global_skills_dir / f"{skill_name}.md"
            global_path.write_text(content, encoding="utf-8")
            logger.info("SkillCreator: Saved global skill to {}", global_path)

            # 2. Also save to workspace/skills/auto-created/[skill_name]/SKILL.md to be discoverable
            workspace_skill_dir = self.workspace_skills_dir / skill_name
            workspace_skill_dir.mkdir(parents=True, exist_ok=True)
            workspace_path = workspace_skill_dir / "SKILL.md"
            workspace_path.write_text(content, encoding="utf-8")
            logger.info("SkillCreator: Saved workspace skill to {}", workspace_path)

            return global_path

        except Exception as e:
            logger.error("SkillCreator: Failed to synthesize skill: {}", e)
            return None
