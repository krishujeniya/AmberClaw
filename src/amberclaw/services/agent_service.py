"""Agent service encapsulating agent registration, cataloging, and direct messaging."""

from pathlib import Path

from loguru import logger

from amberclaw.providers.litellm_client import LLMMessage, LLMRouter
from amberclaw.schemas.agent import AgentProfile
from amberclaw.storage.persistence import JSONStateStore


class AgentService:
    """Service providing high-level business operations for agent lifecycle and agent-specific conversations."""

    def __init__(
        self,
        agent_store: JSONStateStore[AgentProfile] | None = None,
        llm_router: LLMRouter | None = None,
    ) -> None:
        self.agent_store = agent_store or JSONStateStore(
            Path("data/agents.json"), AgentProfile
        )
        self.llm_router = llm_router or LLMRouter()

    def spawn_agent(self, profile: AgentProfile) -> AgentProfile:
        """Register and activate a new agent profile in the store."""
        if self.agent_store.contains(profile.agent_id):
            raise ValueError(f"Agent '{profile.agent_id}' already active.")

        self.agent_store.set(profile.agent_id, profile)
        logger.info(
            "Agent [{}] '{}' successfully spawned into active store",
            profile.agent_id,
            profile.name,
        )
        return profile

    def get_agent(self, agent_id: str) -> AgentProfile | None:
        """Retrieve an agent profile by ID."""
        return self.agent_store.get(agent_id)

    def list_agents(
        self,
        limit: int = 50,
        offset: int = 0,
        order_by: str = "agent_id",
    ) -> list[AgentProfile]:
        """List active agents with deterministic sorting and pagination."""
        all_agents = list(self.agent_store.get_all().values())
        if order_by == "name":
            all_agents.sort(key=lambda a: a.name.lower())
        else:
            all_agents.sort(key=lambda a: a.agent_id)
        return all_agents[offset : offset + limit]

    def delete_agent(self, agent_id: str) -> bool:
        """Remove an agent profile from the store."""
        if not self.agent_store.contains(agent_id):
            return False
        self.agent_store.delete(agent_id)
        logger.info("Agent [{}] deleted from active store", agent_id)
        return True

    async def chat_with_agent(
        self,
        agent_id: str,
        message: str,
    ) -> tuple[str, str]:
        """Send a prompt to a specific agent and receive its response. Returns (reply, agent_id)."""
        agent = self.get_agent(agent_id)
        if not agent:
            raise KeyError(f"Agent '{agent_id}' not found or inactive.")

        messages = [
            LLMMessage(role="system", content=f"You are {agent.name}. {agent.role}"),
            LLMMessage(role="user", content=message),
        ]

        reply = await self.llm_router.generate(
            messages=messages,
            model=agent.model_name,
        )
        return reply, agent_id
