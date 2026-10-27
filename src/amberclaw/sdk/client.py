"""AmberClaw Python Client SDK.

Provides synchronous and asynchronous programmatic client interfaces
for the AmberClaw Autonomous Agent AI OS Gateway.
"""

import json
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx

from amberclaw.sdk.exceptions import (
    AmberClawAPIError,
    AmberClawAuthError,
    AmberClawConnectionError,
)


def _parse_error_response(response: httpx.Response) -> AmberClawAPIError:
    """Parse standard AmberClaw error envelopes."""
    status_code = response.status_code
    try:
        data = response.json()
        if isinstance(data, dict) and "error" in data:
            err = data["error"]
            if isinstance(err, dict):
                return AmberClawAPIError(
                    message=err.get("message", response.text),
                    code=err.get("code", "HTTP_ERROR"),
                    status_code=status_code,
                    request_id=err.get("request_id"),
                    details=err.get("details"),
                )
    except Exception:  # noqa: S110
        pass
    return AmberClawAPIError(
        message=response.text or f"HTTP {status_code} Error",
        code=f"HTTP_{status_code}",
        status_code=status_code,
    )


class AsyncAmberClawClient:
    """Asynchronous client for interacting with the AmberClaw Gateway."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str | None = None,
        token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.token = token
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._build_headers(),
            timeout=self.timeout,
        )

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "AmberClaw-Python-SDK/1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        elif self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    async def __aenter__(self) -> "AsyncAmberClawClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client session."""
        await self._client.aclose()

    async def health(self) -> dict[str, Any]:
        """Check Gateway health and liveness."""
        try:
            res = await self._client.get("/health")
            if res.is_error:
                raise _parse_error_response(res)
            return res.json()
        except httpx.RequestError as e:
            raise AmberClawConnectionError(f"Failed to reach Gateway: {e}") from e

    async def get_metrics(self) -> str:
        """Fetch Prometheus formatted metrics."""
        try:
            res = await self._client.get("/metrics")
            if res.is_error:
                raise _parse_error_response(res)
            return res.text
        except httpx.RequestError as e:
            raise AmberClawConnectionError(f"Failed to fetch metrics: {e}") from e

    async def get_providers_health(self) -> dict[str, Any]:
        """Fetch LLM providers health status."""
        try:
            res = await self._client.get("/api/v1/providers/health")
            if res.status_code in (401, 403):
                raise AmberClawAuthError("Unauthorized access to provider health")
            if res.is_error:
                raise _parse_error_response(res)
            return res.json()
        except httpx.RequestError as e:
            raise AmberClawConnectionError(f"Failed to reach Gateway: {e}") from e

    async def chat(
        self,
        message: str,
        model: str = "gpt-4o",
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Send a synchronous chat request."""
        payload: dict[str, Any] = {"message": message, "model": model}
        if session_id:
            payload["session_id"] = session_id

        try:
            res = await self._client.post("/api/v1/chat", json=payload)
            if res.status_code in (401, 403):
                raise AmberClawAuthError("Invalid credentials or unauthorized chat access")
            if res.is_error:
                raise _parse_error_response(res)
            return res.json()
        except httpx.RequestError as e:
            raise AmberClawConnectionError(f"Chat request failed: {e}") from e

    async def chat_stream(
        self,
        message: str,
        model: str = "gpt-4o",
        session_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream chat tokens via Server-Sent Events (SSE)."""
        payload: dict[str, Any] = {"message": message, "model": model}
        if session_id:
            payload["session_id"] = session_id

        try:
            async with self._client.stream("POST", "/api/v1/chat/stream", json=payload) as response:
                if response.status_code in (401, 403):
                    raise AmberClawAuthError("Unauthorized stream request")
                if response.is_error:
                    await response.aread()
                    raise _parse_error_response(response)

                buffer = ""
                current_event = "token"
                async for chunk in response.aiter_text():
                    buffer += chunk
                    while "\n\n" in buffer:
                        frame_str, buffer = buffer.split("\n\n", 1)
                        lines = frame_str.strip().split("\n")
                        current_data = "{}"
                        for line in lines:
                            if line.startswith("event:"):
                                current_event = line.split(":", 1)[1].strip()
                            elif line.startswith("data:"):
                                current_data = line.split(":", 1)[1].strip()

                        try:
                            parsed_data = json.loads(current_data)
                        except json.JSONDecodeError:
                            parsed_data = {"raw": current_data}

                        yield {"event": current_event, "data": parsed_data}

        except httpx.RequestError as e:
            raise AmberClawConnectionError(f"Stream connection failed: {e}") from e

    async def list_agents(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """List configured agent profiles."""
        try:
            res = await self._client.get("/api/v1/agents", params={"limit": limit, "offset": offset})
            if res.is_error:
                raise _parse_error_response(res)
            return res.json()
        except httpx.RequestError as e:
            raise AmberClawConnectionError(f"Failed to list agents: {e}") from e

    async def get_agent(self, agent_id: str) -> dict[str, Any]:
        """Retrieve a specific agent profile."""
        try:
            res = await self._client.get(f"/api/v1/agents/{agent_id}")
            if res.is_error:
                raise _parse_error_response(res)
            return res.json()
        except httpx.RequestError as e:
            raise AmberClawConnectionError(f"Failed to get agent {agent_id}: {e}") from e

    async def delete_memory(
        self,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Permanent memory purge (GDPR Right-to-be-Forgotten)."""
        params: dict[str, Any] = {}
        if session_id:
            params["session_id"] = session_id
        if user_id:
            params["user_id"] = user_id

        try:
            res = await self._client.delete("/api/v1/memory", params=params)
            if res.is_error:
                raise _parse_error_response(res)
            return res.json()
        except httpx.RequestError as e:
            raise AmberClawConnectionError(f"Failed to delete memory: {e}") from e


class AmberClawClient:
    """Synchronous client wrapper for interacting with the AmberClaw Gateway."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str | None = None,
        token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.token = token
        self.timeout = timeout
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=self._build_headers(),
            timeout=self.timeout,
        )

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "AmberClaw-Python-SDK/1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        elif self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def __enter__(self) -> "AmberClawClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP client session."""
        self._client.close()

    def health(self) -> dict[str, Any]:
        """Check Gateway health and liveness."""
        try:
            res = self._client.get("/health")
            if res.is_error:
                raise _parse_error_response(res)
            return res.json()
        except httpx.RequestError as e:
            raise AmberClawConnectionError(f"Failed to reach Gateway: {e}") from e

    def get_metrics(self) -> str:
        """Fetch Prometheus formatted metrics."""
        try:
            res = self._client.get("/metrics")
            if res.is_error:
                raise _parse_error_response(res)
            return res.text
        except httpx.RequestError as e:
            raise AmberClawConnectionError(f"Failed to fetch metrics: {e}") from e

    def get_providers_health(self) -> dict[str, Any]:
        """Fetch LLM providers health status."""
        try:
            res = self._client.get("/api/v1/providers/health")
            if res.status_code in (401, 403):
                raise AmberClawAuthError("Unauthorized access to provider health")
            if res.is_error:
                raise _parse_error_response(res)
            return res.json()
        except httpx.RequestError as e:
            raise AmberClawConnectionError(f"Failed to reach Gateway: {e}") from e

    def chat(
        self,
        message: str,
        model: str = "gpt-4o",
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Send a synchronous chat request."""
        payload: dict[str, Any] = {"message": message, "model": model}
        if session_id:
            payload["session_id"] = session_id

        try:
            res = self._client.post("/api/v1/chat", json=payload)
            if res.status_code in (401, 403):
                raise AmberClawAuthError("Invalid credentials or unauthorized chat access")
            if res.is_error:
                raise _parse_error_response(res)
            return res.json()
        except httpx.RequestError as e:
            raise AmberClawConnectionError(f"Chat request failed: {e}") from e

    def chat_stream(
        self,
        message: str,
        model: str = "gpt-4o",
        session_id: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Stream chat tokens via Server-Sent Events (SSE)."""
        payload: dict[str, Any] = {"message": message, "model": model}
        if session_id:
            payload["session_id"] = session_id

        try:
            with self._client.stream("POST", "/api/v1/chat/stream", json=payload) as response:
                if response.status_code in (401, 403):
                    raise AmberClawAuthError("Unauthorized stream request")
                if response.is_error:
                    response.read()
                    raise _parse_error_response(response)

                buffer = ""
                current_event = "token"
                for chunk in response.iter_text():
                    buffer += chunk
                    while "\n\n" in buffer:
                        frame_str, buffer = buffer.split("\n\n", 1)
                        lines = frame_str.strip().split("\n")
                        current_data = "{}"
                        for line in lines:
                            if line.startswith("event:"):
                                current_event = line.split(":", 1)[1].strip()
                            elif line.startswith("data:"):
                                current_data = line.split(":", 1)[1].strip()

                        try:
                            parsed_data = json.loads(current_data)
                        except json.JSONDecodeError:
                            parsed_data = {"raw": current_data}

                        yield {"event": current_event, "data": parsed_data}

        except httpx.RequestError as e:
            raise AmberClawConnectionError(f"Stream connection failed: {e}") from e

    def list_agents(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """List configured agent profiles."""
        try:
            res = self._client.get("/api/v1/agents", params={"limit": limit, "offset": offset})
            if res.is_error:
                raise _parse_error_response(res)
            return res.json()
        except httpx.RequestError as e:
            raise AmberClawConnectionError(f"Failed to list agents: {e}") from e

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        """Retrieve a specific agent profile."""
        try:
            res = self._client.get(f"/api/v1/agents/{agent_id}")
            if res.is_error:
                raise _parse_error_response(res)
            return res.json()
        except httpx.RequestError as e:
            raise AmberClawConnectionError(f"Failed to get agent {agent_id}: {e}") from e

    def delete_memory(
        self,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Permanent memory purge (GDPR Right-to-be-Forgotten)."""
        params: dict[str, Any] = {}
        if session_id:
            params["session_id"] = session_id
        if user_id:
            params["user_id"] = user_id

        try:
            res = self._client.delete("/api/v1/memory", params=params)
            if res.is_error:
                raise _parse_error_response(res)
            return res.json()
        except httpx.RequestError as e:
            raise AmberClawConnectionError(f"Failed to delete memory: {e}") from e
