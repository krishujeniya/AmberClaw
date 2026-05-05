import logging
from collections.abc import AsyncGenerator

from pydantic import BaseModel

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
    """
    Centralized Model Router for AmberClaw AI OS.
    Uses LiteLLM to abstract away provider-specific APIs (OpenAI, Anthropic, Gemini, Local, etc.).
    """
    def __init__(self, default_model: str = "gpt-4o"):
        self.default_model = default_model
        if not acompletion:
            logger.warning("litellm is not installed. LLM routing will fail.")

    async def generate(self, messages: list[LLMMessage], model: str = None, temperature: float = 0.7, **kwargs) -> str:
        """
        Generate a synchronous text response from the configured LLM.
        """
        target_model = model or self.default_model
        formatted_messages = [{"role": m.role, "content": m.content} for m in messages]
        
        logger.debug(f"Routing LLM request to {target_model}")
        try:
            response = await acompletion(
                model=target_model,
                messages=formatted_messages,
                temperature=temperature,
                **kwargs,
            )
            return response.choices[0].message.content
        except RateLimitError:
            logger.error(f"Rate limit exceeded for model {target_model}")
            raise
        except ContextWindowExceededError:
            logger.error(f"Context window exceeded for model {target_model}")
            raise
        except Exception as e:
            logger.error(f"Error during LLM generation: {e}")
            raise

    async def generate_stream(self, messages: list[LLMMessage], model: str = None, temperature: float = 0.7, **kwargs) -> AsyncGenerator[str, None]:
        """
        Generate a streaming text response from the configured LLM.
        """
        target_model = model or self.default_model
        formatted_messages = [{"role": m.role, "content": m.content} for m in messages]
        
        logger.debug(f"Routing streaming LLM request to {target_model}")
        try:
            response_stream = await acompletion(
                model=target_model,
                messages=formatted_messages,
                temperature=temperature,
                stream=True,
                **kwargs,
            )
            async for chunk in response_stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Error during streaming LLM generation: {e}")
            raise
