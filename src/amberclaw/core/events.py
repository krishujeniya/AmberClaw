"""AmberClaw Typed Domain Events & Async Event Bus.

Provides typed, versioned domain events with correlation tracking,
along with pattern-matching async event distribution.
"""

import asyncio
import contextlib
import uuid
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class DomainEventType(StrEnum):
    # Agent lifecycle
    AGENT_CREATED = "agent.created"
    AGENT_DELETED = "agent.deleted"
    AGENT_UPDATED = "agent.updated"

    # Task & Execution
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"

    # Tools
    TOOL_EXECUTED = "tool.executed"

    # Governance
    TICKET_CREATED = "ticket.created"
    TICKET_RESOLVED = "ticket.resolved"

    # Memory
    MEMORY_MUTATION = "memory.mutation"

    # System
    SYSTEM_ALERT = "system.alert"


class DomainEvent(BaseModel):
    """Base model for typed, versioned domain events with tracing context."""

    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    event_type: str
    version: str = "1.0"
    timestamp_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str = Field(default_factory=lambda: f"corr_{uuid.uuid4().hex[:12]}")
    source: str = "kernel"
    payload: dict[str, Any] = Field(default_factory=dict)


# Specific typed events
class AgentCreatedEvent(DomainEvent):
    event_type: str = DomainEventType.AGENT_CREATED.value
    agent_id: str
    name: str
    model_name: str
    role: str = ""


class AgentDeletedEvent(DomainEvent):
    event_type: str = DomainEventType.AGENT_DELETED.value
    agent_id: str


class TaskStartedEvent(DomainEvent):
    event_type: str = DomainEventType.TASK_STARTED.value
    task_id: str
    agent_id: str
    session_id: str = "default"


class TaskCompletedEvent(DomainEvent):
    event_type: str = DomainEventType.TASK_COMPLETED.value
    task_id: str
    agent_id: str
    status: str = "success"
    duration_s: float = 0.0


class ToolExecutedEvent(DomainEvent):
    event_type: str = DomainEventType.TOOL_EXECUTED.value
    tool_name: str
    agent_id: str
    status: str = "success"
    duration_s: float = 0.0


class TicketCreatedEvent(DomainEvent):
    event_type: str = DomainEventType.TICKET_CREATED.value
    ticket_id: str
    requester_id: str
    description: str


class TicketResolvedEvent(DomainEvent):
    event_type: str = DomainEventType.TICKET_RESOLVED.value
    ticket_id: str
    status: str
    reviewer_id: str


class MemoryMutationEvent(DomainEvent):
    event_type: str = DomainEventType.MEMORY_MUTATION.value
    action: str  # add_turn, delete_session, purge
    session_id: str
    count: int = 1


# Backward compatibility with existing Event
class Event(BaseModel):
    """Legacy base event model."""

    name: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DomainEventBus:
    """Async Event Bus with exact and wildcard pattern matching (* and prefix.*)."""

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable[..., Any]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    def subscribe(self, event_pattern: str, callback: Callable[..., Any]) -> None:
        """Subscribe a handler to an exact event name or pattern (e.g. 'agent.*' or '*')."""
        self._listeners[event_pattern].append(callback)

    def unsubscribe(self, event_pattern: str, callback: Callable[..., Any]) -> bool:
        """Unsubscribe a previously registered handler."""
        if event_pattern in self._listeners and callback in self._listeners[event_pattern]:
            self._listeners[event_pattern].remove(callback)
            return True
        return False

    async def emit(self, event: DomainEvent | Event) -> int:
        """Emit a domain event to all matching exact and wildcard subscribers."""
        event_name = event.event_type if isinstance(event, DomainEvent) else event.name
        callbacks_to_invoke: list[Callable[..., Any]] = []

        # Find matching subscriptions
        for pattern, funcs in self._listeners.items():
            if pattern in ("*", event_name) or (pattern.endswith(".*") and event_name.startswith(pattern[:-2])):
                callbacks_to_invoke.extend(funcs)

        if not callbacks_to_invoke:
            return 0

        tasks = []
        for cb in callbacks_to_invoke:
            if asyncio.iscoroutinefunction(cb):
                tasks.append(cb(event))
            else:
                with contextlib.suppress(Exception):
                    cb(event)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        return len(callbacks_to_invoke)


# Alias legacy EventBus to DomainEventBus for full backward compatibility
EventBus = DomainEventBus

# Global event bus instance
bus = DomainEventBus()
