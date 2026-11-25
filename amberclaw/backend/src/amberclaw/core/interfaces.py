# ruff: noqa: PLR0913
"""AmberClaw Core Standard Interfaces & Protocols.

Defines stable, runtime-checkable typing protocols for providers, channels,
tools, memory persistence, and execution backends.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ProviderInterface(Protocol):
    """Protocol for language model providers."""

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Execute chat completion."""
        ...

    def get_default_model(self) -> str:
        """Return the default model name."""
        ...

    def get_available_models(self) -> list[str]:
        """Return list of supported models."""
        ...


@runtime_checkable
class ChannelInterface(Protocol):
    """Protocol for messaging channel adapters."""

    name: str

    async def start(self) -> None:
        """Start the channel listener."""
        ...

    async def stop(self) -> None:
        """Stop the channel and clean up resources."""
        ...

    async def send(self, msg: Any) -> None:
        """Send an outbound message."""
        ...


@runtime_checkable
class ToolInterface(Protocol):
    """Protocol for agent tools."""

    @property
    def name(self) -> str:
        """Tool name identifier."""
        ...

    @property
    def description(self) -> str:
        """Human-readable tool description."""
        ...

    @property
    def parameters(self) -> dict[str, Any]:
        """JSON Schema of parameters."""
        ...

    async def execute(self, **kwargs: Any) -> str:
        """Execute tool action and return text result."""
        ...


@runtime_checkable
class MemoryInterface(Protocol):
    """Protocol for session and turn memory persistence."""

    async def aadd_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        turn_index: int | None = None,
        metadata: dict[str, Any] | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        org_id: str | None = None,
    ) -> int:
        """Asynchronously record a turn in the session."""
        ...

    async def aget_turns(
        self,
        session_id: str,
        limit: int = 50,
        offset: int = 0,
        descending: bool = False,
        org_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Asynchronously retrieve turns for a session."""
        ...

    async def asearch_turns(
        self,
        query: str,
        session_id: str | None = None,
        limit: int = 20,
        org_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Asynchronously search conversation history."""
        ...

    async def adelete_session(self, session_id: str) -> bool:
        """Asynchronously delete an entire session history."""
        ...


@runtime_checkable
class ExecutionBackendInterface(Protocol):
    """Protocol for isolated terminal execution backends."""

    async def execute_bash(self, command: str, timeout: int = 30) -> dict[str, Any]:
        """Execute a bash command in isolated environment."""
        ...

    async def execute_python(
        self,
        code: str,
        timeout: int = 30,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute python code in isolated environment."""
        ...
