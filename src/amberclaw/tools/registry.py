"""
AmberClaw Tool Registry and Base Class
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, Field


class BaseTool(ABC):
    """Abstract base class for all AmberClaw tools."""
    
    name: str
    description: str
    args_schema: Optional[Type[BaseModel]] = None
    sandbox: Optional[Any] = None

    def __init__(self, sandbox: Optional[Any] = None):
        self.sandbox = sandbox

    @abstractmethod
    async def run(self, **kwargs) -> str:
        """Execute the tool."""
        pass


class ToolRegistry:
    """Registry for managing and looking up tools."""
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        """Register a new tool."""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all_tool_definitions(self) -> list:
        """Return tool definitions for LLM tool calling."""
        definitions = []
        for tool in self._tools.values():
            definition = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                }
            }
            if tool.args_schema:
                definition["function"]["parameters"] = tool.args_schema.model_json_schema()
            definitions.append(definition)
        return definitions

# Global registry instance
registry = ToolRegistry()
