import logging
from collections.abc import AsyncGenerator

from pydantic import BaseModel

from amberclaw.providers.resilience import CircuitOpenError, get_circuit_breaker

try:
    from litellm import acompletion
    from litellm.exceptions import ContextWindowExceededError, RateLimitError
except ImportError:
    acompletion = None

logger = logging.getLogger(__name__)


class LLMMessage(BaseModel):
    role: str
    content: str


class LLMRouter:
    """Centralized Model Router for AmberClaw AI OS.

    Uses LiteLLM to abstract away provider-specific APIs (OpenAI, Anthropic, Gemini, Local, etc.)
    with automatic CircuitBreaker fault isolation.
    """

    def __init__(self, default_model: str = "gpt-4o"):
        self.default_model = default_model
        if not acompletion:
            logger.warning("litellm is not installed. LLM routing will fail.")

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        fallback_fn: object | None = None,
        **kwargs,
    ) -> str:
        """Generate a synchronous text response from the configured LLM with circuit breaker protection."""
        target_model = model or self.default_model
        formatted_messages = [{"role": m.role, "content": m.content} for m in messages]
        circuit = get_circuit_breaker(f"llm_{target_model}")

        async def _execute_call() -> str:
            logger.debug(f"Routing LLM request to {target_model}")
            response = await acompletion(
                model=target_model,
                messages=formatted_messages,
                temperature=temperature,
                **kwargs,
            )
            # Log token usage metrics if returned by provider
            usage = getattr(response, "usage", None)
            if usage:
                prompt_tokens = getattr(usage, "prompt_tokens", 0)
                completion_tokens = getattr(usage, "completion_tokens", 0)
                total_tokens = getattr(usage, "total_tokens", 0)
                logger.info(
                    f"LLM Token Usage [{target_model}]: "
                    f"prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}"
                )
            return response.choices[0].message.content

        try:
            return await circuit.call_async(_execute_call, fallback_fn=fallback_fn)
        except (RateLimitError, ContextWindowExceededError):
            raise
        except Exception as e:
            logger.error(f"Error during LLM generation for {target_model}: {e}")
            raise

    async def generate_stream(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming text response from the configured LLM."""
        target_model = model or self.default_model
        formatted_messages = [{"role": m.role, "content": m.content} for m in messages]
        circuit = get_circuit_breaker(f"llm_{target_model}")

        if not circuit.can_execute():
            raise CircuitOpenError(circuit.name, circuit.recovery_timeout_s)

        logger.debug(f"Routing streaming LLM request to {target_model}")
        try:
            response_stream = await acompletion(
                model=target_model,
                messages=formatted_messages,
                temperature=temperature,
                stream=True,
                **kwargs,
            )
            circuit.record_success()
            async for chunk in response_stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            circuit.record_failure(e)
            logger.error(f"Error during streaming LLM generation: {e}")
            raise
