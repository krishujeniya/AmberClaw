"""Meta-tools for dynamic tool discovery, schema inspection, and documentation retrieval."""

import json

from pydantic import BaseModel, Field

from amberclaw.tools.registry import BaseTool, ToolRegistry


class ListToolsArgs(BaseModel):
    """Arguments for listing available registered tools."""

    filter_text: str | None = Field(
        default=None, description="Optional text filter for tool names or descriptions"
    )


class ListToolsTool(BaseTool):
    """Tool that returns catalog of all registered tools."""

    name = "list_tools"
    description = "List all available system tools, their parameters, and descriptions."
    args_schema = ListToolsArgs

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        super().__init__()
        self.registry = registry

    async def run(self, filter_text: str | None = None) -> str:
        """Query registry and return tool listing."""
        if not self.registry:
            return "No tool registry configured."

        definitions = self.registry.get_all_tool_definitions()
        if not definitions:
            return "No tools are currently registered in the agent registry."

        lines = ["### Available Tools:"]
        for defn in definitions:
            fn = defn.get("function", {})
            t_name = fn.get("name", "unknown")
            t_desc = fn.get("description", "No description")

            if filter_text:
                q = filter_text.lower()
                if q not in t_name.lower() and q not in t_desc.lower():
                    continue

            lines.append(f"- **{t_name}**: {t_desc}")

        if len(lines) == 1:
            return f"No tools matching filter '{filter_text}' found."

        return "\n".join(lines)


class InspectToolSchemaArgs(BaseModel):
    """Arguments for inspecting schema of a specific tool."""

    tool_name: str = Field(..., description="Name of the tool to inspect")


class InspectToolSchemaTool(BaseTool):
    """Tool that returns the exact JSON schema of a registered tool."""

    name = "inspect_tool_schema"
    description = "Inspect the JSON parameters schema and types for a specific tool."
    args_schema = InspectToolSchemaArgs

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        super().__init__()
        self.registry = registry

    async def run(self, tool_name: str) -> str:
        """Look up tool in registry and return parameter schema."""
        if not self.registry:
            return "No tool registry configured."

        tool = self.registry.get_tool(tool_name)
        if not tool:
            return f"Tool '{tool_name}' not found in registry."

        schema = tool.args_schema.model_json_schema() if tool.args_schema else {}
        output = {
            "name": tool.name,
            "description": tool.description,
            "parameters": schema,
        }
        return json.dumps(output, indent=2)
