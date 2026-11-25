from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from amberclaw.api.deps import get_chat_service
from amberclaw.api.stream.sse import create_sse_response
from amberclaw.services.chat_service import ChatService

router = APIRouter()
llm_router = get_chat_service().llm_router


class ChatStreamRequest(BaseModel):
    message: str
    agent_id: str | None = None
    model: str | None = None
    system_prompt: str | None = None
    temperature: float = 0.7
    raw_completion: bool = False


class ChatMessageRequest(BaseModel):
    message: str
    agent_id: str | None = None
    model: str | None = None
    system_prompt: str | None = None
    temperature: float = 0.7
    raw_completion: bool = False


class ChatMessageResponse(BaseModel):
    reply: str
    model: str
    agent_id: str | None = None


@router.post("", response_model=ChatMessageResponse)
async def chat_completion(
    request: ChatMessageRequest,
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatMessageResponse:
    """Synchronous chat completion routing through canonical runtime or model completion."""
    try:
        reply, model_name = await chat_service.generate_response(
            message=request.message,
            agent_id=request.agent_id,
            model=request.model,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            raw_completion=request.raw_completion,
        )
        return ChatMessageResponse(
            reply=reply,
            model=model_name,
            agent_id=request.agent_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/stream")
async def chat_stream(
    request: ChatStreamRequest,
    chat_service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    """Server-Sent Events (SSE) streaming chat endpoint emitting token and terminal frames."""
    return create_sse_response(
        chat_service.stream_response(
            message=request.message,
            agent_id=request.agent_id,
            model=request.model,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            raw_completion=request.raw_completion,
        )
    )
