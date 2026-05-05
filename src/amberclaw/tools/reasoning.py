"""
AmberClaw Reasoning Tools (Multi-Model & Recursive)
"""
import asyncio

from pydantic import BaseModel, Field

from amberclaw.models.message import Message
from amberclaw.providers.registry import registry as provider_registry
from amberclaw.tools.registry import BaseTool


class CouncilArgs(BaseModel):
    query: str = Field(..., description="The question or task to put to the council.")
    models: list[str] | None = Field(
        None, 
        description="List of model IDs to consult. Default: use configured defaults.",
    )
    depth: int = Field(default=1, ge=1, le=3, description="Number of peer-ranking rounds.")


class CouncilTool(BaseTool):
    name = "council_consensus"
    description = "Run a multi-model council to get a high-confidence answer through peer ranking and synthesis."
    args_schema = CouncilArgs

    async def run(self, query: str, models: list[str] | None = None, depth: int = 1) -> str:
        actual_models = models or ["gpt-4o", "claude-3-5-sonnet-20240620"]
        
        # Stage 1: Collect
        tasks = []
        for model in actual_models:
            provider = provider_registry.get_provider(model)
            tasks.append(provider.generate([Message(role="user", content=query)]))
        
        responses = await asyncio.gather(*tasks)
        results = [{"model": m, "content": r.message.content} for m, r in zip(actual_models, responses)]
        
        # Stage 2: Synthesis (Simplified for production OS)
        synthesis_prompt = (
            f"Synthesize a final answer from these expert opinions on: {query}\n\n"
            + "\n\n".join([f"Expert ({r['model']}): {r['content']}" for r in results])
        )
        
        primary_provider = provider_registry.get_default_provider()
        final_response = await primary_provider.generate([Message(role="user", content=synthesis_prompt)])
        
        return final_response.message.content + f"\n\n---\n*Council synthesized from {len(results)} experts.*"


class MythosArgs(BaseModel):
    query: str = Field(..., description="The question or problem to reason through deeply.")
    depth: int = Field(default=3, ge=1, le=5, description="Reasoning depth.")


class MythosTool(BaseTool):
    name = "mythos_think"
    description = "Perform deep, multi-layer recursive reasoning to uncover hidden insights and edge cases."
    args_schema = MythosArgs

    async def run(self, query: str, depth: int = 3) -> str:
        context = f"Initial Query: {query}\n"
        provider = provider_registry.get_default_provider()

        for i in range(1, depth + 1):
            prompt = (
                f"{context}\n"
                f"Depth {i}/{depth}: Analyze more deeply. Find assumptions and edge cases."
            )
            response = await provider.generate([Message(role="user", content=prompt)])
            thought = response.message.content
            context += f"\nReasoning Layer {i}:\n{thought}\n"

        synthesis_prompt = (
            f"{context}\n"
            "Final Synthesis: Provide the definitive conclusion based on all layers above."
        )
        final_response = await provider.generate([Message(role="user", content=synthesis_prompt)])
        
        return final_response.message.content + f"\n\n---\n*Mythos reasoning completed at depth {depth}.*"
