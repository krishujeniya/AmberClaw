from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from amberclaw.providers.litellm_client import LLMMessage, LLMRouter
from amberclaw.schemas.agent import AgentProfile
from amberclaw.storage.persistence import JSONStateStore

router = APIRouter()
llm_router = LLMRouter()

# Persistent state store for active agents
agent_store = JSONStateStore(Path("data/agents.json"), AgentProfile)


class ChatRequest(BaseModel):
    message: str
    user_id: str


class ChatResponse(BaseModel):
    reply: str
    agent_id: str


@router.post("/spawn", response_model=AgentProfile)
async def spawn_agent(profile: AgentProfile):
    """
    Spawns a new AmberClaw Agent into the OS environment.
    """
    if agent_store.contains(profile.agent_id):
        raise HTTPException(status_code=400, detail="Agent ID already active.")

    agent_store.set(profile.agent_id, profile)
    return profile


@router.get("", response_model=list[AgentProfile])
async def list_agents(
    limit: int = 50,
    offset: int = 0,
    order_by: str = "agent_id",
):
    """
    List all registered active agents with pagination and deterministic ordering.
    """
    all_agents = list(agent_store.get_all().values())
    if order_by == "name":
        all_agents.sort(key=lambda a: a.name.lower())
    else:
        all_agents.sort(key=lambda a: a.agent_id)
    return all_agents[offset : offset + limit]


@router.post("/{agent_id}/chat", response_model=ChatResponse)
async def agent_chat(agent_id: str, request: ChatRequest):
    """
    Send a message to a specific agent and get an LLM response.
    """
    agent = agent_store.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found or inactive.")

    # Construct the LLM payload
    messages = [
        LLMMessage(role="system", content=f"You are {agent.name}. {agent.role}"),
        LLMMessage(role="user", content=request.message),
    ]

    try:
        reply = await llm_router.generate(messages=messages, model=agent.model_name)
        return ChatResponse(reply=reply, agent_id=agent_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
