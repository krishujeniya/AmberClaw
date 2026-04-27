"""A2A Tool for inter-agent communication."""

from typing import Any, Type
from pydantic import BaseModel, Field
from amberclaw.agent.tools.base import PydanticTool
from amberclaw.agent.a2a import A2AManager

class A2ASendArgs(BaseModel):
    target_url: str = Field(..., description="The A2A endpoint of the target agent.")
    method: str = Field(..., description="The method to call on the remote agent.")
    params: dict[str, Any] = Field(default_factory=dict, description="Parameters for the method.")

class A2ATool(PydanticTool):
    """Tool for sending messages to other agents via A2A protocol."""

    def __init__(self, manager: A2AManager):
        self._manager = manager

    @property
    def name(self) -> str:
        return "a2a_send"

    @property
    def description(self) -> str:
        return "Send a message to another AI agent using the A2A protocol."

    @property
    def args_schema(self) -> Type[BaseModel]:
        return A2ASendArgs

    async def run(self, args: A2ASendArgs) -> str:
        try:
            result = await self._manager.send_message(
                args.target_url,
                args.method,
                args.params
            )
            return f"A2A Response: {result}"
        except Exception as e:
            return f"Error sending A2A message: {str(e)}"

class A2ADiscoverArgs(BaseModel):
    network: str = Field("local", description="Network to scan (e.g., 'local').")

class A2ADiscoveryTool(PydanticTool):
    """Tool for discovering other agents."""

    def __init__(self, manager: A2AManager):
        self._manager = manager

    @property
    def name(self) -> str:
        return "a2a_discover"

    @property
    def description(self) -> str:
        return "Discover other agents on the network supporting A2A."

    @property
    def args_schema(self) -> Type[BaseModel]:
        return A2ADiscoverArgs

    async def run(self, args: A2ADiscoverArgs) -> str:
        # Placeholder for discovery logic (e.g. mDNS or a registry)
        peers = [f"{p.name} ({p.id}) at {p.endpoints.get('a2a', 'N/A')}" for p in self._manager.peers.values()]
        if not peers:
            return "No agents discovered yet."
        return "Discovered Agents:\n" + "\n".join(peers)
