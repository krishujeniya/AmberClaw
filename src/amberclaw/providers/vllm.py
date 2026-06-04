"""vLLM provider and local model runner implementation."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlparse

import httpx
from loguru import logger

from amberclaw.providers.base import LLMResponse
from amberclaw.providers.litellm_provider import LiteLLMProvider


class VLLMLocalRunner:
    """Manages the life-cycle of a local vLLM OpenAI-compatible server process."""

    def __init__(
        self,
        model: str,
        api_base: str,
        quantization: str | None = None,
        speculative_model: str | None = None,
        num_speculative_tokens: int | None = None,
    ):
        self.model = model
        self.api_base = api_base
        self.quantization = quantization
        self.speculative_model = speculative_model
        self.num_speculative_tokens = num_speculative_tokens

        # Parse host and port from api_base
        parsed = urlparse(self.api_base)
        self.host = parsed.hostname or "localhost"
        self.port = parsed.port or 8000
        self.process: asyncio.subprocess.Process | None = None

    def is_local_base(self) -> bool:
        """Check if api_base points to a localhost or loopback interface."""
        return self.host in ("localhost", "127.0.0.1", "0.0.0.0")

    def build_command_args(self, use_binary: bool = False) -> list[str]:
        """Build command arguments for launching the vLLM server."""
        if use_binary:
            args = ["vllm", "serve", self.model]
        else:
            args = ["python", "-m", "vllm.entrypoints.openai.api_server", "--model", self.model]

        args.extend(["--host", self.host])
        args.extend(["--port", str(self.port)])

        if self.quantization:
            args.extend(["--quantization", self.quantization])
        if self.speculative_model:
            args.extend(["--speculative-model", self.speculative_model])
        if self.num_speculative_tokens is not None:
            args.extend(["--num-speculative-tokens", str(self.num_speculative_tokens)])

        return args

    async def start(self) -> None:
        """Launch the local vLLM subprocess."""
        if self.process is not None:
            return

        args = self.build_command_args(use_binary=False)
        logger.info(f"Launching local vLLM process: {' '.join(args)}")
        try:
            self.process = await asyncio.create_subprocess_exec(
                args[0],
                *args[1:],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, ProcessLookupError):
            logger.warning("vLLM module not found or failed to start via python, trying 'vllm serve'...")
            binary_args = self.build_command_args(use_binary=True)
            try:
                self.process = await asyncio.create_subprocess_exec(
                    binary_args[0],
                    *binary_args[1:],
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            except Exception as e:
                logger.error(f"Failed to start vLLM server using 'vllm serve': {e}")
                self.process = None

    async def stop(self) -> None:
        """Cleanly terminate the local vLLM process."""
        if self.process is not None:
            logger.info("Stopping local vLLM process...")
            try:
                self.process.terminate()
                await self.process.wait()
            except Exception as e:
                logger.warning(f"Error terminating vLLM process: {e}")
            self.process = None

    async def check_health(self) -> bool:
        """Query vLLM health status endpoint."""
        parsed = urlparse(self.api_base)
        health_url = f"{parsed.scheme}://{parsed.netloc}/health"
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(health_url)
                return res.status_code == 200
        except Exception:
            # Fallback to models list endpoint
            models_url = self.api_base
            if not models_url.endswith("/"):
                models_url += "/"
            models_url += "models"
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    res = await client.get(models_url)
                    return res.status_code == 200
            except Exception:
                return False

    async def wait_for_ready(self, timeout: int = 120) -> bool:
        """Wait until the vLLM server is healthy and responding."""
        elapsed = 0
        interval = 2
        while elapsed < timeout:
            if await self.check_health():
                return True
            await asyncio.sleep(interval)
            elapsed += interval
        return False


class VLLMProvider(LiteLLMProvider):
    """vLLM provider which inherits from LiteLLMProvider but manages a local runner."""

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "vllm",
        quantization: str | None = None,
        speculative_model: str | None = None,
        num_speculative_tokens: int | None = None,
        **kwargs: Any,
    ):
        base_url = api_base or "http://localhost:8000/v1"
        super().__init__(
            api_key=api_key or "no-key",
            api_base=base_url,
            default_model=default_model,
            **kwargs,
        )
        self.runner = VLLMLocalRunner(
            model=default_model,
            api_base=base_url,
            quantization=quantization,
            speculative_model=speculative_model,
            num_speculative_tokens=num_speculative_tokens,
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        response_format: dict[str, Any] | None = None,
        on_token: Callable[[str], Awaitable[None]] | None = None,
    ) -> LLMResponse:
        """Execute chat request, launching local runner if loopback base is not healthy."""
        if self.runner.is_local_base():
            if not await self.runner.check_health():
                logger.info("Local vLLM server not running, launching process...")
                await self.runner.start()
                ready = await self.runner.wait_for_ready()
                if not ready:
                    return LLMResponse(
                        content="Local vLLM runner failed to become ready.",
                        finish_reason="error",
                    )

        # Standard LiteLLM Provider execution
        return await super().chat(
            messages=messages,
            tools=tools,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
            response_format=response_format,
            on_token=on_token,
        )
