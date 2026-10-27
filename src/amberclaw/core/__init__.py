"""
AmberClaw amberclaw.core module.
"""

from pydantic import BaseModel, Field

from amberclaw.core.concurrency import (
    ControlledThreadPool,
    DeadlineContext,
    StructuredTaskGroup,
    TaskRegistry,
)
from amberclaw.core.events import (
    AgentCreatedEvent,
    AgentDeletedEvent,
    DomainEvent,
    DomainEventBus,
    DomainEventType,
    MemoryMutationEvent,
    TaskCompletedEvent,
    TaskStartedEvent,
    TicketCreatedEvent,
    TicketResolvedEvent,
    ToolExecutedEvent,
)
from amberclaw.core.interfaces import (
    ChannelInterface,
    ExecutionBackendInterface,
    MemoryInterface,
    ProviderInterface,
    ToolInterface,
)
from amberclaw.core.kernel import ClawOSSupervisor


class CoreModuleConfig(BaseModel):
    """Configuration for the amberclaw.core module."""

    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = [
    "AgentCreatedEvent",
    "AgentDeletedEvent",
    "ChannelInterface",
    "ClawOSSupervisor",
    "ControlledThreadPool",
    "CoreModuleConfig",
    "DeadlineContext",
    "DomainEvent",
    "DomainEventBus",
    "DomainEventType",
    "ExecutionBackendInterface",
    "MemoryInterface",
    "MemoryMutationEvent",
    "ProviderInterface",
    "StructuredTaskGroup",
    "TaskCompletedEvent",
    "TaskRegistry",
    "TaskStartedEvent",
    "TicketCreatedEvent",
    "TicketResolvedEvent",
    "ToolExecutedEvent",
    "ToolInterface",
]
