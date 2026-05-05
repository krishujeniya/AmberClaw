"""
AmberClaw Agent-to-Agent (A2A) Communication Protocol
"""
import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


class AgentMessage(BaseModel):
    """Message sent between agents."""
    sender_id: str
    receiver_id: str | None = None  # None means broadcast
    topic: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class AgentNetworking:
    """Manages agent discovery and communication."""
    
    def __init__(self):
        self._agents: dict[str, Callable] = {}
        self._topics: dict[str, list[str]] = {} # topic -> list of agent_ids

    def register_agent(self, agent_id: str, callback: Callable):
        """Register an agent for receiving messages."""
        self._agents[agent_id] = callback
        logger.info(f"Agent {agent_id} registered for networking")

    def subscribe(self, agent_id: str, topic: str):
        """Subscribe an agent to a specific topic."""
        if topic not in self._topics:
            self._topics[topic] = []
        if agent_id not in self._topics[topic]:
            self._topics[topic].append(agent_id)
        logger.debug(f"Agent {agent_id} subscribed to topic: {topic}")

    async def send(self, message: AgentMessage):
        """Send a message to a specific agent or broadcast to a topic."""
        if message.receiver_id:
            # Direct message
            if message.receiver_id in self._agents:
                await self._deliver(message.receiver_id, message)
            else:
                logger.warning(f"Target agent {message.receiver_id} not found")
        # Broadcast to topic
        elif message.topic in self._topics:
            tasks = [
                self._deliver(agent_id, message) 
                for agent_id in self._topics[message.topic]
                if agent_id != message.sender_id # Don't send back to sender
            ]
            if tasks:
                await asyncio.gather(*tasks)

    async def _deliver(self, agent_id: str, message: AgentMessage):
        """Deliver a message to an agent's callback."""
        if agent_id in self._agents:
            try:
                callback = self._agents[agent_id]
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
            except Exception as e:
                logger.error(f"Failed to deliver message to agent {agent_id}: {e}")

# Global networking instance
network = AgentNetworking()
