"""
AmberClaw Subagent Tools
"""

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from amberclaw.agent.subagent import SubagentManager
from amberclaw.tools.registry import BaseTool


class SpawnArgs(BaseModel):
    task: str = Field(..., description="The task for the subagent to complete")
    label: str | None = Field(None, description="Optional short label for the task")
    model: str | None = Field(
        None, description="Optional specific model for the subagent"
    )
    worker_role: str | None = Field(
        None, description="Optional specialized worker role"
    )


class SpawnTool(BaseTool[[str, str | None, str | None, str | None]]):
    name = "spawn"
    description = "Spawn a subagent to handle a task in the background."
    args_schema = SpawnArgs

    def __init__(self, manager: "SubagentManager | None" = None) -> None:
        super().__init__()
        self._manager = manager

    async def run(
        self,
        task: str,
        label: str | None = None,
        model: str | None = None,
        worker_role: str | None = None,
    ) -> str:
        if self._manager is None:
            return "Error: No subagent manager configured."
        return await self._manager.spawn(
            task=task, label=label, model=model, worker_role=worker_role
        )
