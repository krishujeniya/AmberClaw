"""Legacy keyword API adapters over the canonical injected reasoning tools."""

from pydantic import BaseModel, Field

from amberclaw.agent.tools.council import CouncilArgs as AgentCouncilArgs
from amberclaw.agent.tools.council import CouncilTool as AgentCouncilTool
from amberclaw.agent.tools.mythos import MythosArgs
from amberclaw.agent.tools.mythos import MythosTool as AgentMythosTool
from amberclaw.providers.base import LLMProvider
from amberclaw.tools.registry import BaseTool


class CouncilArgs(BaseModel):
    """Preserve the legacy nullable model selection contract."""

    query: str = Field(..., description="The question or task to put to the council.")
    models: list[str] | None = Field(
        None,
        description="List of model IDs to consult. Default: use configured defaults.",
    )
    depth: int = Field(
        default=1, ge=1, le=3, description="Number of peer-ranking rounds."
    )


class CouncilTool(BaseTool[[str, list[str] | None, int]]):
    name = "council_consensus"
    description = "Run a multi-model council through peer ranking and synthesis."
    args_schema = CouncilArgs

    def __init__(
        self, provider: LLMProvider | None = None, model: str | None = None
    ) -> None:
        super().__init__()
        self._council = (
            AgentCouncilTool(provider, model or provider.get_default_model())
            if provider is not None
            else None
        )

    async def run(
        self, query: str, models: list[str] | None = None, depth: int = 1
    ) -> str:
        if self._council is None:
            return "Error: No LLM provider configured."
        return await self._council.run(
            AgentCouncilArgs(query=query, models=models or [], depth=depth)
        )


class MythosTool(BaseTool[[str, int]]):
    name = "mythos_think"
    description = "Perform multi-layer recursive reasoning and synthesize the result."
    args_schema = MythosArgs

    def __init__(
        self, provider: LLMProvider | None = None, model: str | None = None
    ) -> None:
        super().__init__()
        self._mythos = (
            AgentMythosTool(provider, model or provider.get_default_model())
            if provider is not None
            else None
        )

    async def run(self, query: str, depth: int = 3) -> str:
        if self._mythos is None:
            return "Error: No LLM provider configured."
        return await self._mythos.run(MythosArgs(query=query, depth=depth))
