"""
AmberClaw Subagent Tools
"""
from typing import Optional
from pydantic import BaseModel, Field
from amberclaw.tools.registry import BaseTool
from amberclaw.agent.subagent import manager as subagent_manager


class SpawnArgs(BaseModel):
    task: str = Field(..., description="The task for the subagent to complete")
    label: Optional[str] = Field(None, description="Optional short label for the task")
    model: Optional[str] = Field(None, description="Optional specific model for the subagent")


class SpawnTool(BaseTool):
    name = "spawn"
    description = "Spawn a subagent to handle a task in the background."
    args_schema = SpawnArgs

    async def run(self, task: str, label: Optional[str] = None, model: Optional[str] = None) -> str:
        return await subagent_manager.spawn(task=task, label=label, model=model)
