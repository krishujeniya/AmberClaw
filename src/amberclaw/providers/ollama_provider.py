"""Ollama provider implementation for local multimodal LLMs."""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

import httpx
import json_repair
from loguru import logger

from amberclaw.providers.base import LLMProvider, LLMResponse, ToolCallRequest

_OLLAMA_MSG_KEYS = frozenset({"role", "content", "images", "tool_calls"})


class OllamaProvider(LLMProvider):
    """
    Ollama provider for local execution.

    Features:
    - Supports multimodal (vision) by converting OpenAI content list to Ollama images field
    - Supports tool calling (if supported by the local model)
    - Directly calls Ollama /api/chat endpoint
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "llama3",
    ):
        super().__init__(api_key, api_base)
        # Default Ollama address
        self.api_base = api_base or "http://localhost:11434"
        if not self.api_base.endswith("/"):
            self.api_base += "/"
        self.default_model = default_model

    def _prepare_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert OpenAI multimodal format to Ollama format."""
        processed = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            tool_calls = msg.get("tool_calls")

            clean_msg: dict[str, Any] = {"role": role}

            if isinstance(content, list):
                # Multimodal list content
                text_parts = []
                images = []
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif item.get("type") == "image_url":
                        url = item.get("image_url", {}).get("url", "")
                        if url.startswith("data:"):
                            # Extract base64 part: data:image/jpeg;base64,XXXX
                            try:
                                b64 = url.split(",", 1)[1]
                                images.append(b64)
                            except IndexError:
                                pass

                clean_msg["content"] = "\n".join(text_parts)
                if images:
                    clean_msg["images"] = images
            else:
                clean_msg["content"] = content

            if tool_calls:
                clean_msg["tool_calls"] = tool_calls

            processed.append(clean_msg)
        return processed

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        on_token: Callable[[str], Awaitable[None]] | None = None,
    ) -> LLMResponse:
        """Send a chat completion request to Ollama."""
        target_model = model or self.default_model
        # Strip provider prefix if present (e.g. ollama/llama3 -> llama3)
        if "/" in target_model and target_model.startswith("ollama/"):
            target_model = target_model.split("/", 1)[1]

        url = f"{self.api_base}api/chat"

        payload = {
            "model": target_model,
            "messages": self._prepare_messages(messages),
            "stream": on_token is not None,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }

        if tools:
            payload["tools"] = tools

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                if on_token:
                    return await self._handle_streaming(client, url, payload, on_token)
                else:
                    response = await client.post(url, json=payload)
                    if response.status_code != 200:
                        return LLMResponse(
                            content=f"Ollama Error {response.status_code}: {response.text}",
                            finish_reason="error",
                        )

                    data = response.json()
                    return self._parse_ollama_response(data)

        except Exception as e:
            logger.exception("Ollama call failed")
            return LLMResponse(
                content=f"Error calling Ollama: {repr(e)}",
                finish_reason="error",
            )

    async def _handle_streaming(
        self,
        client: httpx.AsyncClient,
        url: str,
        payload: dict[str, Any],
        on_token: Callable[[str], Awaitable[None]],
    ) -> LLMResponse:
        """Handle streaming response from Ollama."""
        full_content = ""
        tool_calls_raw = []
        finish_reason = "stop"
        usage = {}

        async with client.stream("POST", url, json=payload) as response:
            if response.status_code != 200:
                body = await response.aread()
                return LLMResponse(
                    content=f"Ollama Streaming Error {response.status_code}: {body.decode()}",
                    finish_reason="error",
                )

            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    if chunk.get("done"):
                        usage = {
                            "prompt_tokens": chunk.get("prompt_eval_count", 0),
                            "completion_tokens": chunk.get("eval_count", 0),
                            "total_tokens": chunk.get("prompt_eval_count", 0)
                            + chunk.get("eval_count", 0),
                        }
                        break

                    msg = chunk.get("message", {})
                    token = msg.get("content", "")
                    if token:
                        full_content += token
                        await on_token(token)

                    if msg.get("tool_calls"):
                        tool_calls_raw.extend(msg["tool_calls"])

                except json.JSONDecodeError:
                    continue

        # Parse tool calls if any
        tool_calls = []
        for tc in tool_calls_raw:
            func = tc.get("function", {})
            args = func.get("arguments", {})
            if isinstance(args, str):
                args = json_repair.loads(args)

            tool_calls.append(
                ToolCallRequest(
                    id=tc.get("id", f"call_{len(tool_calls)}"),
                    name=func.get("name"),
                    arguments=args if isinstance(args, dict) else {"raw": str(args)},
                )
            )

        return LLMResponse(
            content=full_content, tool_calls=tool_calls, finish_reason=finish_reason, usage=usage
        )

    def _parse_ollama_response(self, data: dict[str, Any]) -> LLMResponse:
        """Parse non-streaming Ollama response."""
        msg = data.get("message", {})
        content = msg.get("content")

        tool_calls = []
        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                func = tc.get("function", {})
                args = func.get("arguments", {})
                if isinstance(args, str):
                    args = json_repair.loads(args)

                tool_calls.append(
                    ToolCallRequest(
                        id=tc.get("id", f"call_{len(tool_calls)}"),
                        name=func.get("name"),
                        arguments=args if isinstance(args, dict) else {"raw": str(args)},
                    )
                )

        usage = {
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
            "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
        }

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason="stop" if data.get("done") else "length",
            usage=usage,
        )

    def get_default_model(self) -> str:
        return self.default_model

    def to_langchain_chat(self, model: str | None = None, **kwargs: Any) -> Any:
        """Convert this provider to a LangChain ChatOllama model."""
        from langchain_ollama import ChatOllama

        target_model = model or self.default_model
        if "/" in target_model and target_model.startswith("ollama/"):
            target_model = target_model.split("/", 1)[1]

        return ChatOllama(
            model=target_model,
            base_url=self.api_base,
            **kwargs,
        )
