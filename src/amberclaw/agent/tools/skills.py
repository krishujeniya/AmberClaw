"""Skill management tools: search, install, list."""

import asyncio
import re
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
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
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

    def __init__(self, workspace: str, loader: Any | None = None) -> None:
        super().__init__()
        self.workspace = workspace
        self.loader = loader

    async def run(self, args: SkillInstallArgs) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.slug):
            return "Error: Skill slug must be a single name without paths or options."
        if not await asyncio.to_thread(self._safe_install_path, args.slug):
            return "Error: Skill install path is outside the workspace skill directory."
        try:
            # Ensure workspace exists without blocking the event loop.
            await asyncio.to_thread(
                Path(self.workspace).mkdir, parents=True, exist_ok=True
            )

            logger.info("Installing skill '{}' to {}", args.slug, self.workspace)
            cmd = [
                "npx",
                "--yes",
                "clawhub@latest",
                "install",
                args.slug,
                "--workdir",
                self.workspace,
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
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
                    security_info = (
                        "\n\n[WARNING] Security scan found risks:\n- "
                        + "\n- ".join(warnings)
                    )
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

    def _safe_install_path(self, slug: str) -> bool:
        try:
            workspace = Path(self.workspace).resolve()
            skills = (workspace / "skills").resolve()
            destination = (skills / slug).resolve()
            return skills.is_relative_to(workspace) and destination.is_relative_to(
                skills
            )
        except (OSError, RuntimeError, ValueError):
            return False


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

    def __init__(self, workspace: str) -> None:
        super().__init__()
        self.workspace = workspace

    async def run(self, args: SkillListArgs) -> str:  # noqa: ARG002 - empty tool arguments preserve the tool protocol
        try:
            cmd = [
                "npx",
                "--yes",
                "clawhub@latest",
                "list",
                "--workdir",
                self.workspace,
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
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

    def __init__(self, workspace: str) -> None:
        super().__init__()
        self.workspace = Path(workspace)
        self.global_skills_dir = Path.home() / ".amberclaw" / "skills" / "auto-created"
        self.workspace_skills_dir = self.workspace / "skills" / "auto-created"
        self.workspace_root_skills_dir = self.workspace / "skills"

    async def run(self, args: SkillManageArgs) -> str:
        return await asyncio.to_thread(self._validate_and_manage, args)

    def _validate_and_manage(self, args: SkillManageArgs) -> str:
        for name in (args.skill_name, args.target_skill_name):
            if name is not None and not self._safe_skill_paths(name):
                return "Error: Skill name or path is outside the allowed skill directories."
        return self._manage_skill(args)

    def _safe_skill_paths(self, name: str) -> bool:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
            return False
        roots_and_paths = (
            (self.global_skills_dir, self.global_skills_dir / f"{name}.md"),
            (self.workspace_skills_dir, self.workspace_skills_dir / name),
            (self.workspace_skills_dir, self.workspace_skills_dir / name / "SKILL.md"),
            (self.workspace_root_skills_dir, self.workspace_root_skills_dir / name),
            (
                self.workspace_root_skills_dir,
                self.workspace_root_skills_dir / name / "SKILL.md",
            ),
        )
        try:
            workspace = self.workspace.resolve()
            if not all(
                root.resolve().is_relative_to(workspace)
                for root in (self.workspace_skills_dir, self.workspace_root_skills_dir)
            ):
                return False
            return all(
                path.resolve().is_relative_to(root.resolve())
                for root, path in roots_and_paths
            )
        except (OSError, RuntimeError, ValueError):
            return False

    def _manage_skill(self, args: SkillManageArgs) -> str:
        if args.action == "delete":
            return self._delete_skill(args.skill_name)
        if args.action == "edit":
            if not args.content:
                return "Error: Content is required for the 'edit' action."
            self._write_skill(args.skill_name, args.content)
            return f"Successfully updated/created skill '{args.skill_name}' content."
        return self._merge_skill(args)

    def _delete_skill(self, skill_name: str) -> str:
        deleted_paths = []
        global_path = self.global_skills_dir / f"{skill_name}.md"
        if global_path.exists():
            global_path.unlink()
            deleted_paths.append(str(global_path))
        for root in (self.workspace_skills_dir, self.workspace_root_skills_dir):
            directory = root / skill_name
            if directory.exists():
                shutil.rmtree(directory)
                deleted_paths.append(str(directory))
        if deleted_paths:
            return f"Successfully deleted skill '{skill_name}' from:\n" + "\n".join(
                deleted_paths
            )
        return f"Skill '{skill_name}' not found."

    def _write_skill(self, name: str, content: str) -> None:
        self.global_skills_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_skills_dir.mkdir(parents=True, exist_ok=True)
        (self.global_skills_dir / f"{name}.md").write_text(content, encoding="utf-8")
        directory = self.workspace_skills_dir / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "SKILL.md").write_text(content, encoding="utf-8")

    def _merge_skill(self, args: SkillManageArgs) -> str:
        target = args.target_skill_name
        if not target:
            return "Error: target_skill_name is required for the 'merge' action."
        source = args.skill_name
        src_content = self._load_skill_content(source)
        tgt_content = self._load_skill_content(target)
        if not src_content:
            return f"Error: Source skill '{source}' not found."
        if not tgt_content:
            return f"Error: Target skill '{target}' not found."
        merged_name = f"merged-{source}-and-{target}"
        if not self._safe_skill_paths(merged_name):
            return "Error: Merged skill path is outside the allowed skill directories."
        merged_content = args.content or (
            "---\n"
            f"name: {merged_name}\n"
            f"description: Merged skill combining {source} and {target}\n"
            "---\n"
            f"# Merged Skill: {source} and {target}\n\n"
            "## Prerequisite Skills\n"
            f"- {source}\n"
            f"- {target}\n\n"
            "## Combined Steps\n\n"
            f"### Part 1: {source}\n"
            f"{src_content}\n\n"
            f"### Part 2: {target}\n"
            f"{tgt_content}\n"
        )
        self._write_skill(merged_name, merged_content)
        self._delete_skill(source)
        self._delete_skill(target)
        return f"Successfully merged '{source}' and '{target}' into new skill '{merged_name}'."

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
