"""
AmberClaw Agent Core
"""

from loguru import logger
from pydantic import BaseModel

from amberclaw.core.events import Event, bus
from amberclaw.core.networking import AgentMessage, network
from amberclaw.models.message import Message, MessageRole


class AgentState(BaseModel):
    """Current state of the agent."""

    is_busy: bool = False
    current_task: str | None = None
    last_action: str | None = None


class BaseAgent:
    """Base class for all AmberClaw agents."""

    def __init__(self, id: str, name: str) -> None:  # noqa: A002
        self.id = id
        self.name = name
        self.state = AgentState()
        # Register with networking
        network.register_agent(self.id, self.handle_agent_message)

    async def handle_agent_message(self, message: AgentMessage) -> None:
        """Process messages received from other agents."""
        logger.info(
            f"Agent {self.id} received message from {message.sender_id} on topic {message.topic}"
        )

    async def handle_message(self, message: Message) -> Message:
        """Process an incoming message and return a response."""
        await bus.emit(
            Event(
                name="agent.message_received",
                payload={"agent_id": self.id, "message": message.model_dump()},
            )
        )

        # Placeholder for agent logic
        response = Message(
            role=MessageRole.ASSISTANT,
            content=f"Hello, I am {self.name}. I received your message: {message.content}",
        )

        await bus.emit(
            Event(
                name="agent.response_sent",
                payload={"agent_id": self.id, "response": response.model_dump()},
            )
        )
        return response

    async def run_task(self, task: str) -> None:
        """Execute a long-running task."""
        self.state.is_busy = True
        self.state.current_task = task
        try:
            await bus.emit(
                Event(
                    name="agent.task_started",
                    payload={"agent_id": self.id, "task": task},
                )
            )
            # Task execution logic here
            pass
        finally:
            self.state.is_busy = False
            self.state.current_task = None
            await bus.emit(
                Event(
                    name="agent.task_completed",
                    payload={"agent_id": self.id, "task": task},
                )
            )
