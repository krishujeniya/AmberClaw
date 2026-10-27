from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from amberclaw.api.stream.protocol import done_frame, error_frame, token_frame
from amberclaw.api.stream.sse import create_sse_response
from amberclaw.providers.litellm_client import LLMMessage, LLMRouter
from amberclaw.schemas.agent import AgentProfile
from amberclaw.storage.persistence import JSONStateStore

router = APIRouter()
llm_router = LLMRouter()
agent_store = JSONStateStore(Path("data/agents.json"), AgentProfile)


class ChatStreamRequest(BaseModel):
    message: str
    agent_id: str | None = None
    model: str | None = None
    system_prompt: str | None = None
    temperature: float = 0.7


class ChatMessageRequest(BaseModel):
    message: str
    agent_id: str | None = None
    model: str | None = None
    system_prompt: str | None = None
    temperature: float = 0.7


class ChatMessageResponse(BaseModel):
    reply: str
    model: str
    agent_id: str | None = None


@router.post("", response_model=ChatMessageResponse)
async def chat_completion(request: ChatMessageRequest) -> ChatMessageResponse:
    """Synchronous chat completion."""
    model_name = request.model or "gpt-4o"
    system_content = request.system_prompt or "You are AmberClaw AI Assistant."

    if request.agent_id:
        agent = agent_store.get(request.agent_id)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{request.agent_id}' not found.",
            )
        model_name = request.model or agent.model_name
        system_content = f"You are {agent.name}. {agent.role}"

    messages = [
        LLMMessage(role="system", content=system_content),
        LLMMessage(role="user", content=request.message),
    ]

    try:
        reply = await llm_router.generate(
            messages=messages,
            model=model_name,
            temperature=request.temperature,
        )
        return ChatMessageResponse(
            reply=reply,
            model=model_name,
            agent_id=request.agent_id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e


@router.post("/stream")
async def chat_stream(request: ChatStreamRequest):
    """Server-Sent Events (SSE) streaming chat endpoint emitting token and terminal frames."""
    model_name = request.model or "gpt-4o"
    system_content = request.system_prompt or "You are AmberClaw AI Assistant."

    if request.agent_id:
        agent = agent_store.get(request.agent_id)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{request.agent_id}' not found.",
            )
        model_name = request.model or agent.model_name
        system_content = f"You are {agent.name}. {agent.role}"

    messages = [
        LLMMessage(role="system", content=system_content),
        LLMMessage(role="user", content=request.message),
    ]

    async def _event_generator() -> AsyncGenerator[str, None]:
        chunk_index = 0
        try:
            async for chunk in llm_router.generate_stream(
                messages=messages,
                model=model_name,
                temperature=request.temperature,
            ):
                frame = token_frame(content=chunk, index=chunk_index)
                yield frame.to_sse()
                chunk_index += 1

            # Emit final completion frame
            yield done_frame(total_tokens=chunk_index).to_sse()
        except Exception as err:
            yield error_frame(error_message=str(err)).to_sse()

    return create_sse_response(_event_generator())
