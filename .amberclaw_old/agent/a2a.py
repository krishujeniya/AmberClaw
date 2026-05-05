"""Agent-to-Agent (A2A) Protocol implementation."""

import uuid
from typing import Any, Optional, Callable
from pydantic import BaseModel, Field
import httpx
from loguru import logger

class AgentCard(BaseModel):
    """Machine-readable agent manifest."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    version: str = "1.0.0"
    capabilities: list[str] = []
    endpoints: dict[str, str] = {}
    metadata: dict[str, Any] = {}

class A2AMessage(BaseModel):
    """JSON-RPC 2.0 based message."""
    jsonrpc: str = "2.0"
    method: str
    params: dict[str, Any] = {}
    id: Optional[str] = None

class A2AResponse(BaseModel):
    """JSON-RPC 2.0 based response."""
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[dict[str, Any]] = None
    id: Optional[str] = None

class A2AManager:
    """Manages A2A communication and peer discovery."""

    def __init__(self, card: AgentCard):
        self.card = card
        self.peers: dict[str, AgentCard] = {}
        self._handlers: dict[str, Callable] = {}

    def register_handler(self, method: str, handler: Callable):
        """Register a handler for an incoming A2A method."""
        self._handlers[method] = handler

    async def send_message(self, target_url: str, method: str, params: dict[str, Any]) -> Any:
        """Send an A2A message to a remote agent."""
        msg = A2AMessage(method=method, params=params, id=str(uuid.uuid4()))
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(target_url, json=msg.model_dump(), timeout=30.0)
                if resp.status_code == 200:
                    data = resp.json()
                    response = A2AResponse.model_validate(data)
                    if response.error:
                        raise Exception(f"A2A Error: {response.error}")
                    return response.result
                else:
                    raise Exception(f"HTTP Error {resp.status_code}: {resp.text}")
            except Exception as e:
                logger.error("A2A send failed to {}: {}", target_url, e)
                raise

    async def handle_message(self, message_dict: dict[str, Any]) -> dict[str, Any]:
        """Handle an incoming A2A message."""
        try:
            msg = A2AMessage.model_validate(message_dict)
            handler = self._handlers.get(msg.method)
            if not handler:
                return A2AResponse(
                    error={"code": -32601, "message": "Method not found"},
                    id=msg.id
                ).model_dump()

            result = await handler(msg.params)
            return A2AResponse(result=result, id=msg.id).model_dump()
        except Exception as e:
            logger.exception("A2A handle failed")
            return A2AResponse(
                error={"code": -32603, "message": str(e)},
                id=message_dict.get("id")
            ).model_dump()

    def discover_peer(self, card: AgentCard):
        """Add a discovered peer."""
        self.peers[card.id] = card
        logger.info("A2A: Discovered peer {} ({})", card.name, card.id)
