from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from amberclaw.providers.litellm_client import LLMMessage, LLMRouter
from amberclaw.schemas.agent import AgentProfile

router = APIRouter()
llm_router = LLMRouter()

# Dependency or mock DB for active agents
active_agents = {}

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
    if profile.agent_id in active_agents:
        raise HTTPException(status_code=400, detail="Agent ID already active.")
    
    active_agents[profile.agent_id] = profile
    # Here the OS Heartbeat Engine would register the agent process
    return profile

@router.post("/{agent_id}/chat", response_model=ChatResponse)
async def agent_chat(agent_id: str, request: ChatRequest):
    """
    Send a message to a specific agent and get an LLM response.
    """
    if agent_id not in active_agents:
        raise HTTPException(status_code=404, detail="Agent not found or inactive.")
    
    agent = active_agents[agent_id]
    
    # Construct the LLM payload
    messages = [
        LLMMessage(role="system", content=f"You are {agent.name}. {agent.role}"),
        LLMMessage(role="user", content=request.message),
    ]
    
    try:
        reply = await llm_router.generate(messages=messages, model=agent.model_name)
        return ChatResponse(reply=reply, agent_id=agent_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
