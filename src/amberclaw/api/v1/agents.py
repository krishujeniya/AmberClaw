from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from amberclaw.providers.litellm_client import LLMMessage, LLMRouter
from amberclaw.schemas.agent import AgentProfile
from amberclaw.storage.tenant import (
    CrossTenantAccessViolationError,
    TenantContext,
    TenantIsolatedStateStore,
)

router = APIRouter()
llm_router = LLMRouter()

# Persistent state store for active agents partitioned per tenant
agent_store = TenantIsolatedStateStore(
    Path("data/tenants"), AgentProfile, "agents.json"
)


class ChatRequest(BaseModel):
    message: str
    user_id: str


class ChatResponse(BaseModel):
    reply: str
    agent_id: str


@router.post("/spawn", response_model=AgentProfile)
async def spawn_agent(profile: AgentProfile) -> AgentProfile:
    """
    Spawns a new AmberClaw Agent into the OS environment.
    """
    active_tenant = TenantContext.get_current() or "default"
    try:
        if agent_store.contains(profile.agent_id, tenant_id=active_tenant):
            raise HTTPException(status_code=400, detail="Agent ID already active.")

        agent_store.set(profile.agent_id, profile, tenant_id=active_tenant)
        return profile
    except CrossTenantAccessViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc


@router.get("", response_model=list[AgentProfile])
async def list_agents(
    limit: int = 50,
    offset: int = 0,
    order_by: str = "agent_id",
) -> list[AgentProfile]:
    """
    List all registered active agents with pagination and deterministic ordering.
    """
    active_tenant = TenantContext.get_current() or "default"
    try:
        all_agents = list(agent_store.get_all(tenant_id=active_tenant).values())
        if order_by == "name":
            all_agents.sort(key=lambda a: a.name.lower())
        else:
            all_agents.sort(key=lambda a: a.agent_id)
        return all_agents[offset : offset + limit]
    except CrossTenantAccessViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc


@router.post("/{agent_id}/chat", response_model=ChatResponse)
async def agent_chat(agent_id: str, request: ChatRequest) -> ChatResponse:
    """
    Send a message to a specific agent and get an LLM response.
    """
    active_tenant = TenantContext.get_current() or "default"
    try:
        agent = agent_store.get(agent_id, tenant_id=active_tenant)
    except CrossTenantAccessViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc

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
