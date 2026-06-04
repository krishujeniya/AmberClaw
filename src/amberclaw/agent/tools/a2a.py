"""Tool for Agent-to-Agent task delegation and discovery."""

from typing import Any

from pydantic import BaseModel, Field

from amberclaw.agent.a2a import A2AManager, AgentCard
from amberclaw.agent.learning.a2a import delegate_to_remote
from amberclaw.agent.tools.base import PydanticTool


class A2ADelegateArgs(BaseModel):
    target_url: str = Field(..., description="The remote agent A2A HTTP endpoint URL, e.g. http://localhost:8000/api/v1/a2a")
    task: str = Field(..., description="The task to delegate to the remote agent")


class A2ADelegateTool(PydanticTool):
    """Tool to delegate execution of tasks to another local/remote AmberClaw agent via JSON-RPC 2.0."""

    @property
    def name(self) -> str:
        return "a2a_delegate"

    @property
    def description(self) -> str:
        return (
            "Delegate a task to another remote/local AmberClaw agent. "
            "The remote agent will execute the task in its own isolated environment and return the final output."
        )

    @property
    def args_schema(self) -> type[A2ADelegateArgs]:
        return A2ADelegateArgs

    async def run(self, args: A2ADelegateArgs) -> str:
        try:
            return await delegate_to_remote(args.target_url, args.task)
        except Exception as e:
            return f"Delegation failed: {e}"


class A2AArgs(BaseModel):
    target_url: str = Field(..., description="The remote agent's A2A JSON-RPC URL")
    method: str = Field(..., description="The A2A method to call (e.g. execute_task, get_capabilities)")
    params: dict[str, Any] = Field(default_factory=dict, description="Parameters for the method call")


class A2ATool(PydanticTool):
    """Tool to send A2A messages to registered or remote agents."""

    @property
    def name(self) -> str:
        return "a2a_send"

    @property
    def description(self) -> str:
        return "Send a JSON-RPC message to a remote agent using the A2A protocol."

    @property
    def args_schema(self) -> type[A2AArgs]:
        return A2AArgs

    def __init__(self, a2a_manager: A2AManager):
        super().__init__()
        self.a2a_manager = a2a_manager

    async def run(self, args: A2AArgs) -> str:
        try:
            res = await self.a2a_manager.send_message(args.target_url, args.method, args.params)
            return f"Success: {res}"
        except Exception as e:
            return f"A2A send failed: {e}"


class A2ADiscoveryArgs(BaseModel):
    peer_id: str = Field(..., description="ID of the discovered peer agent")
    name: str = Field(..., description="Name of the peer agent")
    endpoint: str = Field(..., description="A2A HTTP endpoint of the peer agent")


class A2ADiscoveryTool(PydanticTool):
    """Tool to discover and register a peer agent."""

    @property
    def name(self) -> str:
        return "a2a_discover"

    @property
    def description(self) -> str:
        return "Register a newly discovered peer agent in the A2A network."

    @property
    def args_schema(self) -> type[A2ADiscoveryArgs]:
        return A2ADiscoveryArgs

    def __init__(self, a2a_manager: A2AManager):
        super().__init__()
        self.a2a_manager = a2a_manager

    async def run(self, args: A2ADiscoveryArgs) -> str:
        card = AgentCard(
            id=args.peer_id,
            name=args.name,
            endpoints={"a2a": args.endpoint},
        )
        self.a2a_manager.discover_peer(card)
        return f"Successfully registered peer agent {args.name} ({args.peer_id})"
