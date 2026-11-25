"""AmberClaw OS Agent Execution Engine module and execution lifecycle management."""

from enum import StrEnum

from loguru import logger
from pydantic import BaseModel, Field


class EngineState(StrEnum):
    """Lifecycle state of the agent execution engine."""

    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class EngineModuleConfig(BaseModel):
    """Configuration for the amberclaw.engine module."""

    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")
    max_concurrent_tasks: int = Field(default=10, ge=1)
    tool_result_max_chars: int = Field(default=5000, ge=100)


class EngineLifecycleManager:
    """Manages the startup, pause, resume, and teardown of the execution engine."""

    def __init__(self, config: EngineModuleConfig | None = None) -> None:
        self.config = config or EngineModuleConfig()
        self.state = EngineState.INITIALIZING

    def start(self) -> None:
        """Start the execution engine."""
        self.state = EngineState.RUNNING
        logger.info("Agent Execution Engine started (version: {})", self.config.version)

    def pause(self) -> None:
        """Pause active task processing."""
        self.state = EngineState.PAUSED
        logger.info("Agent Execution Engine paused")

    def resume(self) -> None:
        """Resume task processing."""
        self.state = EngineState.RUNNING
        logger.info("Agent Execution Engine resumed")

    def stop(self) -> None:
        """Stop the engine and clean up runtime resources."""
        self.state = EngineState.STOPPED
        logger.info("Agent Execution Engine stopped")


__all__ = [
    "EngineLifecycleManager",
    "EngineModuleConfig",
    "EngineState",
]
