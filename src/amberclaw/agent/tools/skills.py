"""Skill management tools: search, install, list."""

import asyncio
import os
import shutil
from pathlib import Path
from typing import Any, Literal

from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.agent.tools.base import PydanticTool


class SkillSearchArgs(BaseModel):
    """Arguments for skill_search."""
    query: str = Field(..., description="Search query (natural language)")


class SkillSearchTool(PydanticTool):
    """Search ClawHub for available skills."""

    @property
    def name(self) -> str:
        return "skill_search"

    @property
    def description(self) -> str:
        return "Search the ClawHub registry for skills to extend agent capabilities."

    @property
    def args_schema(self) -> type[SkillSearchArgs]:
        return SkillSearchArgs

    async def run(self, args: SkillSearchArgs) -> str:
        try:
            cmd = ["npx", "--yes", "clawhub@latest", "search", args.query]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                err = stderr.decode().strip()
                logger.error("SkillSearch failed: {}", err)
                return f"Error searching skills: {err}"

            return stdout.decode().strip() or "No skills found matching your query."
        except Exception as e:
            logger.exception("SkillSearch exception")
            return f"Error: {e}"


class SkillInstallArgs(BaseModel):
    """Arguments for skill_install."""
    slug: str = Field(..., description="The unique name/slug of the skill to install")


class SkillInstallTool(PydanticTool):
    """Install a skill from ClawHub."""

    @property
    def name(self) -> str:
        return "skill_install"

    @property
    def description(self) -> str:
        return "Install a skill from ClawHub into the workspace. Extends agent tools."

    @property
    def args_schema(self) -> type[SkillInstallArgs]:
        return SkillInstallArgs

    def __init__(self, workspace: str, loader: Any | None = None):
        super().__init__()
        self.workspace = workspace
        self.loader = loader

    async def run(self, args: SkillInstallArgs) -> str:
        try:
            # Ensure workspace exists
            os.makedirs(self.workspace, exist_ok=True)

            logger.info("Installing skill '{}' to {}", args.slug, self.workspace)
            cmd = ["npx", "--yes", "clawhub@latest", "install", args.slug, "--workdir", self.workspace]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                err = stderr.decode().strip()
                logger.error("SkillInstall failed: {}", err)
                return f"Error installing skill: {err}"

            # Post-install check for security (AC-101)
            security_info = ""
            if self.loader:
                warnings = self.loader.scan_skill(args.slug)
                if warnings:
                    security_info = "\n\n[WARNING] Security scan found risks:\n- " + "\n- ".join(warnings)
                else:
                    security_info = "\n\n[SAFE] Security scan passed."

            return (
                f"Successfully installed '{args.slug}'.\n"
                "The new tools will be available in the NEXT session."
                f"{security_info}\n\n"
                f"Details: {stdout.decode().strip()}"
            )
        except Exception as e:
            logger.exception("SkillInstall exception")
            return f"Error: {e}"


class SkillListArgs(BaseModel):
    """Arguments for skill_list."""
    pass


class SkillListTool(PydanticTool):
    """List installed skills."""

    @property
    def name(self) -> str:
        return "skill_list"

    @property
    def description(self) -> str:
        return "List all skills currently installed in the agent's workspace."

    @property
    def args_schema(self) -> type[SkillListArgs]:
        return SkillListArgs

    def __init__(self, workspace: str):
        super().__init__()
        self.workspace = workspace

    async def run(self, args: SkillListArgs) -> str:
        try:
            cmd = ["npx", "--yes", "clawhub@latest", "list", "--workdir", self.workspace]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                err = stderr.decode().strip()
                logger.error("SkillList failed: {}", err)
                return f"Error listing skills: {err}"

            return stdout.decode().strip() or "No skills installed in workspace."
        except Exception as e:
            logger.exception("SkillList exception")
            return f"Error: {e}"


class SkillManageArgs(BaseModel):
    """Arguments for skill_manage."""

    action: Literal["edit", "merge", "delete"] = Field(
        ..., description="Action to perform: 'edit', 'merge', or 'delete'"
    )
    skill_name: str = Field(..., description="Name of the source skill")
    target_skill_name: str | None = Field(
        None, description="Name of the target skill (required for 'merge')"
    )
    content: str | None = Field(
        None, description="New markdown content of the skill (required for 'edit')"
    )


class SkillManageTool(PydanticTool):
    """Exposes capability to edit, merge, or delete agent skills."""

    @property
    def name(self) -> str:
        return "skill_manage"

    @property
    def description(self) -> str:
        return "Manage agent skills: edit content, merge two skills into one, or delete a skill."

    @property
    def args_schema(self) -> type[SkillManageArgs]:
        return SkillManageArgs

    def __init__(self, workspace: str):
        super().__init__()
        self.workspace = Path(workspace)
        self.global_skills_dir = Path.home() / ".amberclaw" / "skills" / "auto-created"
        self.workspace_skills_dir = self.workspace / "skills" / "auto-created"
        self.workspace_root_skills_dir = self.workspace / "skills"

    async def run(self, args: SkillManageArgs) -> str:
        action = args.action
        skill_name = args.skill_name

        if action == "delete":
            # 1. Global path
            global_path = self.global_skills_dir / f"{skill_name}.md"
            deleted_paths = []
            if global_path.exists():
                global_path.unlink()
                deleted_paths.append(str(global_path))

            # 2. Workspace auto-created
            workspace_dir = self.workspace_skills_dir / skill_name
            if workspace_dir.exists():
                shutil.rmtree(workspace_dir)
                deleted_paths.append(str(workspace_dir))

            # 3. Workspace root skill
            root_dir = self.workspace_root_skills_dir / skill_name
            if root_dir.exists():
                shutil.rmtree(root_dir)
                deleted_paths.append(str(root_dir))

            if deleted_paths:
                return f"Successfully deleted skill '{skill_name}' from:\n" + "\n".join(deleted_paths)
            return f"Skill '{skill_name}' not found."

        elif action == "edit":
            if not args.content:
                return "Error: Content is required for the 'edit' action."

            # Make dirs
            self.global_skills_dir.mkdir(parents=True, exist_ok=True)
            self.workspace_skills_dir.mkdir(parents=True, exist_ok=True)

            global_path = self.global_skills_dir / f"{skill_name}.md"
            global_path.write_text(args.content, encoding="utf-8")

            workspace_dir = self.workspace_skills_dir / skill_name
            workspace_dir.mkdir(parents=True, exist_ok=True)
            workspace_path = workspace_dir / "SKILL.md"
            workspace_path.write_text(args.content, encoding="utf-8")

            return f"Successfully updated/created skill '{skill_name}' content."

        elif action == "merge":
            target = args.target_skill_name
            if not target:
                return "Error: target_skill_name is required for the 'merge' action."

            # Find source content
            src_content = self._load_skill_content(skill_name)
            tgt_content = self._load_skill_content(target)

            if not src_content:
                return f"Error: Source skill '{skill_name}' not found."
            if not tgt_content:
                return f"Error: Target skill '{target}' not found."

            merged_name = f"merged-{skill_name}-and-{target}"
            merged_content = ""
            if args.content:
                merged_content = args.content
            else:
                # Automerge by combining frontmatter and content
                merged_content = (
                    "---\n"
                    f"name: {merged_name}\n"
                    f"description: Merged skill combining {skill_name} and {target}\n"
                    "---\n"
                    f"# Merged Skill: {skill_name} and {target}\n\n"
                    "## Prerequisite Skills\n"
                    f"- {skill_name}\n"
                    f"- {target}\n\n"
                    "## Combined Steps\n\n"
                    f"### Part 1: {skill_name}\n"
                    f"{src_content}\n\n"
                    f"### Part 2: {target}\n"
                    f"{tgt_content}\n"
                )

            # Write merged skill
            self.global_skills_dir.mkdir(parents=True, exist_ok=True)
            self.workspace_skills_dir.mkdir(parents=True, exist_ok=True)

            global_path = self.global_skills_dir / f"{merged_name}.md"
            global_path.write_text(merged_content, encoding="utf-8")

            workspace_dir = self.workspace_skills_dir / merged_name
            workspace_dir.mkdir(parents=True, exist_ok=True)
            workspace_path = workspace_dir / "SKILL.md"
            workspace_path.write_text(merged_content, encoding="utf-8")

            # Clean up the original two skills
            await self.run(SkillManageArgs(action="delete", skill_name=skill_name))
            await self.run(SkillManageArgs(action="delete", skill_name=target))

            return f"Successfully merged '{skill_name}' and '{target}' into new skill '{merged_name}'."

        return f"Unknown action: {action}"

    def _load_skill_content(self, skill_name: str) -> str | None:
        """Load content from global or workspace files."""
        global_path = self.global_skills_dir / f"{skill_name}.md"
        if global_path.exists():
            return global_path.read_text(encoding="utf-8")

        workspace_path = self.workspace_skills_dir / skill_name / "SKILL.md"
        if workspace_path.exists():
            return workspace_path.read_text(encoding="utf-8")

        root_path = self.workspace_root_skills_dir / skill_name / "SKILL.md"
        if root_path.exists():
            return root_path.read_text(encoding="utf-8")

        return None
