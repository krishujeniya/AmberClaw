"""Spawn tool for creating background subagents."""

from typing import TYPE_CHECKING, Optional
from pydantic import BaseModel, Field

from amberclaw.agent.tools.base import PydanticTool

if TYPE_CHECKING:
    from amberclaw.agent.subagent import SubagentManager


class SpawnArgs(BaseModel):
    """Arguments for the spawn tool."""

    task: str = Field(..., description="The task for the subagent to complete")
    label: Optional[str] = Field(
        None, description="Optional short label for the task (for display)"
    )
    model: Optional[str] = Field(None, description="Optional: specific model for the subagent")
    reasoning_effort: Optional[str] = Field(
        None, description="Optional: reasoning effort (low, medium, high)"
    )


class SpawnTool(PydanticTool):
    """Tool to spawn a subagent for background task execution."""

    @property
    def name(self) -> str:
        return "spawn"

    @property
    def description(self) -> str:
        return (
            "Spawn a subagent to handle a task in the background. "
            "Use this for complex or time-consuming tasks that can run independently. "
            "The subagent will complete the task and report back when done."
        )

    @property
    def args_schema(self) -> type[SpawnArgs]:
        return SpawnArgs


    def __init__(self, manager: "SubagentManager"):
        super().__init__()
        self._manager = manager
        self._origin_channel = "cli"
        self._origin_chat_id = "direct"
        self._session_key = "cli:direct"

    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the origin context for subagent announcements."""
        self._origin_channel = channel
        self._origin_chat_id = chat_id
        self._session_key = f"{channel}:{chat_id}"

    async def run(self, args: SpawnArgs) -> str:
        """Spawn a subagent to execute the given task."""
        return await self._manager.spawn(
            task=args.task,
            label=args.label,
            origin_channel=self._origin_channel,
            origin_chat_id=self._origin_chat_id,
            session_key=self._session_key,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
        )
