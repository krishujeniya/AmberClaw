"""Skill management tools: search, install, list."""

import asyncio
import os
from typing import Optional, Type, Any
from pydantic import BaseModel, Field
from loguru import logger

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
    def args_schema(self) -> Type[SkillSearchArgs]:
        return SkillSearchArgs

    async def run(self, args: SkillSearchArgs) -> str:
        try:
            cmd = ["npx", "--yes", "clawhub@latest", "search", args.query]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
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
    def args_schema(self) -> Type[SkillInstallArgs]:
        return SkillInstallArgs

    def __init__(self, workspace: str, loader: Optional[Any] = None):
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
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
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
    def args_schema(self) -> Type[SkillListArgs]:
        return SkillListArgs

    def __init__(self, workspace: str):
        super().__init__()
        self.workspace = workspace

    async def run(self, args: SkillListArgs) -> str:
        try:
            cmd = ["npx", "--yes", "clawhub@latest", "list", "--workdir", self.workspace]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
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
