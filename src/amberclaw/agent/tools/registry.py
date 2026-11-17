"""Tool registry for dynamic tool management."""

from collections.abc import ValuesView
from typing import Any, TypeVar

from amberclaw.agent.tools.base import PydanticTool, Tool

T = TypeVar("T", bound=Tool)


class ToolRegistry:
    """
    Registry for agent tools.

    Allows dynamic registration and execution of tools.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """Unregister a tool by name."""
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def values(self) -> ValuesView[Tool]:
        """Get all registered tools."""
        return self._tools.values()

    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def get_definitions(self) -> list[dict[str, Any]]:
        """Get all tool definitions in OpenAI format."""
        return [tool.to_schema() for tool in self._tools.values()]

    async def execute(self, name: str, params: dict[str, Any]) -> str:
        """Execute a tool by name with given parameters."""
        error_hint = "\n\n[Analyze the error above and try a different approach.]"

        tool = self._tools.get(name)
        if not tool:
            return f"Error: Tool '{name}' not found. Available: {', '.join(self.tool_names)}"

        from amberclaw.security.auth import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
            check_tool_permission,
        )

        try:
            check_tool_permission(name)
        except Exception as e:
            return f"Error: {e}" + error_hint

        from amberclaw.config.schema import (  # noqa: PLC0415
            settings,
        )
        from amberclaw.security.approval import (  # noqa: PLC0415
            ApprovalStatus,
            ToolApprovalManager,
            ToolRiskLevel,
        )

        destructive_tools = {"exec", "write_file", "edit_file"}
        if (
            getattr(settings.security, "require_human_approval_for_destructive", True)
            and name in destructive_tools
        ):
            approval_mgr = ToolApprovalManager.get_instance()
            decision = approval_mgr.evaluate_tool_execution(
                tool_name=name,
                agent_id="default_agent",
                args=params,
                risk_level=ToolRiskLevel.HIGH,
            )
            if decision.status == ApprovalStatus.PENDING_APPROVAL:
                return (
                    f"Error: Tool execution blocked: '{name}' requires human approval (ticket: {decision.ticket_id})"
                    + error_hint
                )
            if decision.status == ApprovalStatus.REJECTED:
                return (
                    f"Error: Tool execution rejected: {decision.reason}"
                    + error_hint
                )

        exec_params = {k: v for k, v in params.items() if k != "approval_ticket_id"}

        try:
            # Pydantic tools handle their own internal validation and execution
            if isinstance(tool, PydanticTool):
                result = await tool.execute(**exec_params)
            else:
                # Legacy path for non-pydantic tools
                exec_params = tool.cast_params(exec_params)
                errors = tool.validate_params(exec_params)
                if errors:
                    return (
                        f"Error: Invalid parameters for tool '{name}': "
                        + "; ".join(errors)
                        + error_hint
                    )
                result = await tool.execute(**exec_params)

            if isinstance(result, str) and result.startswith("Error"):
                return result + error_hint
            return result
        except Exception as e:
            return f"Error executing {name}: {e!s}" + error_hint

    @property
    def tool_names(self) -> list[str]:
        """Get list of registered tool names."""
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
