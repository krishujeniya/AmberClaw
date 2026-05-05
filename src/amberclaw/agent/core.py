"""
AmberClaw Agent Core
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from amberclaw.models.message import Message, Conversation
from amberclaw.core.events import bus, Event
from amberclaw.config.schema import settings


class AgentState(BaseModel):
    """Current state of the agent."""
    is_busy: bool = False
    current_task: Optional[str] = None
    last_action: Optional[str] = None


from amberclaw.core.networking import network, AgentMessage

class BaseAgent:
    """Base class for all AmberClaw agents."""
    
    def __init__(self, id: str, name: str):
        self.id = id
        self.name = name
        self.state = AgentState()
        # Register with networking
        network.register_agent(self.id, self.handle_agent_message)

    async def handle_agent_message(self, message: AgentMessage):
        """Process messages received from other agents."""
        logger.info(f"Agent {self.id} received message from {message.sender_id} on topic {message.topic}")
        # Default implementation just logs the message
        pass

    async def handle_message(self, message: Message) -> Message:
        """Process an incoming message and return a response."""
        await bus.emit(Event(name="agent.message_received", payload={"agent_id": self.id, "message": message.model_dump()}))
        
        # Placeholder for agent logic
        response = Message(
            role="assistant",
            content=f"Hello, I am {self.name}. I received your message: {message.content}"
        )
        
        await bus.emit(Event(name="agent.response_sent", payload={"agent_id": self.id, "response": response.model_dump()}))
        return response

    async def run_task(self, task: str):
        """Execute a long-running task."""
        self.state.is_busy = True
        self.state.current_task = task
        try:
            await bus.emit(Event(name="agent.task_started", payload={"agent_id": self.id, "task": task}))
            # Task execution logic here
            pass
        finally:
            self.state.is_busy = False
            self.state.current_task = None
            await bus.emit(Event(name="agent.task_completed", payload={"agent_id": self.id, "task": task}))
