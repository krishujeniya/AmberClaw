"""
AmberClaw Subagent Tools
"""

from pydantic import BaseModel, Field

from amberclaw.agent.subagent import manager as subagent_manager
from amberclaw.tools.registry import BaseTool


class SpawnArgs(BaseModel):
    task: str = Field(..., description="The task for the subagent to complete")
    label: str | None = Field(None, description="Optional short label for the task")
    model: str | None = Field(None, description="Optional specific model for the subagent")
    worker_role: str | None = Field(None, description="Optional specialized worker role")


class SpawnTool(BaseTool):
    name = "spawn"
    description = "Spawn a subagent to handle a task in the background."
    args_schema = SpawnArgs

    async def run(
        self,
        task: str,
        label: str | None = None,
        model: str | None = None,
        worker_role: str | None = None,
    ) -> str:
        return await subagent_manager.spawn(task=task, label=label, model=model, worker_role=worker_role)
