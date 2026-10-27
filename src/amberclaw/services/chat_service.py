"""Chat service encapsulating LLM inference and streaming generation."""

from collections.abc import AsyncGenerator
from pathlib import Path

from loguru import logger

from amberclaw.api.stream.protocol import done_frame, error_frame, token_frame
from amberclaw.providers.litellm_client import LLMMessage, LLMRouter
from amberclaw.schemas.agent import AgentProfile
from amberclaw.storage.persistence import JSONStateStore


class ChatService:
    """Service handling conversational completions and token streaming across models and agents."""

    def __init__(
        self,
        llm_router: LLMRouter | None = None,
        agent_store: JSONStateStore[AgentProfile] | None = None,
    ) -> None:
        self.llm_router = llm_router or LLMRouter()
        self.agent_store = agent_store or JSONStateStore(
            Path("data/agents.json"), AgentProfile
        )

    def _resolve_context(
        self,
        agent_id: str | None,
        model: str | None,
        system_prompt: str | None,
    ) -> tuple[str, str]:
        """Resolve effective model name and system prompt, looking up agent profile if supplied."""
        model_name = model or "gpt-4o"
        system_content = system_prompt or "You are AmberClaw AI Assistant."

        if agent_id:
            agent = self.agent_store.get(agent_id)
            if not agent:
                raise KeyError(f"Agent '{agent_id}' not found.")
            model_name = model or agent.model_name
            system_content = f"You are {agent.name}. {agent.role}"

        return model_name, system_content

    async def generate_response(
        self,
        message: str,
        agent_id: str | None = None,
        model: str | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
    ) -> tuple[str, str]:
        """Generate a complete chat response returning (reply, model_name)."""
        model_name, system_content = self._resolve_context(
            agent_id, model, system_prompt
        )

        messages = [
            LLMMessage(role="system", content=system_content),
            LLMMessage(role="user", content=message),
        ]

        logger.debug(
            "ChatService generating response via model {} (agent: {})",
            model_name,
            agent_id,
        )
        reply = await self.llm_router.generate(
            messages=messages,
            model=model_name,
            temperature=temperature,
        )
        return reply, model_name

    async def stream_response(
        self,
        message: str,
        agent_id: str | None = None,
        model: str | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """Yield Server-Sent Events (SSE) formatted frames for streaming chat responses."""
        try:
            model_name, system_content = self._resolve_context(
                agent_id, model, system_prompt
            )
        except KeyError as exc:
            yield error_frame(error_message=str(exc)).to_sse()
            return

        messages = [
            LLMMessage(role="system", content=system_content),
            LLMMessage(role="user", content=message),
        ]

        chunk_index = 0
        try:
            async for chunk in self.llm_router.generate_stream(
                messages=messages,
                model=model_name,
                temperature=temperature,
            ):
                frame = token_frame(content=chunk, index=chunk_index)
                yield frame.to_sse()
                chunk_index += 1

            yield done_frame(total_tokens=chunk_index).to_sse()
        except Exception as err:
            logger.error("Error during streaming generation: {}", err)
            yield error_frame(error_message=str(err)).to_sse()
