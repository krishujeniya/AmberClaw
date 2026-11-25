"""Chat service encapsulating LLM inference and streaming generation."""

import asyncio
import contextlib
from collections.abc import AsyncGenerator, Awaitable, Callable
from pathlib import Path
from typing import Any, Protocol

from loguru import logger

from amberclaw.api.stream.protocol import done_frame, error_frame, token_frame
from amberclaw.providers.litellm_client import LLMMessage, LLMRouter
from amberclaw.schemas.agent import AgentProfile
from amberclaw.storage.persistence import JSONStateStore
from amberclaw.storage.tenant import TenantIsolatedStateStore


class ChatRuntime(Protocol):
    """Canonical AgentLoop direct-call and streaming callback contract."""

    async def process_direct(
        self,
        content: str,
        *,
        session_key: str,
        channel: str,
        chat_id: str,
        on_token: Callable[[str], Awaitable[None]] | None = None,
    ) -> str: ...


class ChatService:
    """Service handling conversational completions and token streaming across models and agents."""

    def __init__(
        self,
        llm_router: LLMRouter | None = None,
        agent_store: JSONStateStore[AgentProfile] | TenantIsolatedStateStore[AgentProfile] | None = None,
        runtime: ChatRuntime | None = None,
    ) -> None:
        self.llm_router = llm_router or LLMRouter()
        self.agent_store = agent_store or TenantIsolatedStateStore(
            Path("data/tenants"), AgentProfile, "agents.json"
        )
        self.runtime = runtime

    def set_runtime(self, runtime: ChatRuntime | None) -> None:
        """Bind or unbind the canonical agent runtime."""
        self.runtime = runtime

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
        raw_completion: bool = False,
    ) -> tuple[str, str]:
        """Generate a complete chat response returning (reply, model_name)."""
        model_name, system_content = self._resolve_context(
            agent_id, model, system_prompt
        )

        if self.runtime is not None and not raw_completion:
            session_key = f"api:{agent_id or 'default'}"
            logger.debug(
                "Routing API chat request through canonical runtime (session: {})",
                session_key,
            )
            reply = await self.runtime.process_direct(
                content=message,
                session_key=session_key,
                channel="api",
                chat_id=agent_id or "default",
            )
            return reply, model_name

        messages = [
            LLMMessage(role="system", content=system_content),
            LLMMessage(role="user", content=message),
        ]

        logger.debug(
            "ChatService generating response via raw completion model {} (agent: {})",
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
        raw_completion: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Yield Server-Sent Events (SSE) formatted frames for streaming chat responses."""
        try:
            model_name, system_content = self._resolve_context(
                agent_id, model, system_prompt
            )
        except KeyError:
            yield error_frame(error_message=f"Agent '{agent_id}' not found.", code="NOT_FOUND").to_sse()
            return

        if self.runtime is not None and not raw_completion:
            session_key = f"api:{agent_id or 'default'}"
            queue: asyncio.Queue[str | None] = asyncio.Queue()
            emitted = False

            async def on_token(text: str) -> None:
                nonlocal emitted
                if text:
                    emitted = True
                    await queue.put(text)

            async def run() -> None:
                try:
                    result = await self.runtime.process_direct(
                        content=message,
                        session_key=session_key,
                        channel="api",
                        chat_id=agent_id or "default",
                        on_token=on_token,
                    )
                    if not emitted and result:
                        await queue.put(result)
                except asyncio.CancelledError:
                    logger.debug("Runtime processing cancelled by client stream disconnect")
                    raise
                except Exception:
                    logger.exception("Runtime direct processing failed")
                    frame = error_frame(
                        error_message="Chat processing encountered an internal error.",
                        code="STREAM_ERROR",
                    )
                    await queue.put(frame.to_sse())
                finally:
                    await queue.put(None)

            task = asyncio.create_task(run())
            chunk_index = 0
            had_error = False
            try:
                while (chunk := await queue.get()) is not None:
                    if "event: error" in chunk or "STREAM_ERROR" in chunk:
                        had_error = True
                        yield chunk
                    else:
                        frame = token_frame(content=chunk, index=chunk_index)
                        yield frame.to_sse()
                        chunk_index += 1
                if not had_error:
                    yield done_frame(total_tokens=chunk_index).to_sse()
            finally:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
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
        except asyncio.CancelledError:
            logger.debug("Streaming generator cancelled by client disconnect")
            raise
        except Exception:
            logger.exception("Error during raw streaming generation")
            yield error_frame(
                error_message="Streaming generation encountered an internal error.",
                error_code="STREAM_ERROR",
            ).to_sse()
