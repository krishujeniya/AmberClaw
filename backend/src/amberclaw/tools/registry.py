"""
AmberClaw Tool Registry and Base Class
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, ParamSpec

from pydantic import BaseModel

P = ParamSpec("P")


class BaseTool(ABC, Generic[P]):
    """Abstract base class for all AmberClaw tools."""

    name: str
    description: str
    args_schema: type[BaseModel] | None = None
    sandbox: object | None = None

    def __init__(self, sandbox: object | None = None) -> None:
        self.sandbox = sandbox

    @abstractmethod
    async def run(self, *args: P.args, **kwargs: P.kwargs) -> str:
        """Execute the tool."""
        pass


class ToolRegistry:
    """Registry for managing and looking up tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool[...]] = {}

    def register(self, tool: BaseTool[...]) -> None:
        """Register a new tool."""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> BaseTool[...] | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all_tool_definitions(self) -> list[dict[str, Any]]:
        """Return tool definitions for LLM tool calling."""
        definitions = []
        for tool in self._tools.values():
            definition: dict[str, Any] = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                },
            }
            if tool.args_schema:
                definition["function"]["parameters"] = (
                    tool.args_schema.model_json_schema()
                )
            definitions.append(definition)
        return definitions


# Global registry instance
registry = ToolRegistry()
