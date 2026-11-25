"""
AmberClaw Toolsets Configuration
"""

from typing import TYPE_CHECKING

from amberclaw.providers.base import LLMProvider

if TYPE_CHECKING:
    from amberclaw.agent.subagent import SubagentManager
from amberclaw.tools.data_science import DataCleanTool
from amberclaw.tools.filesystem import (
    FilesystemSandbox,
    ListDirTool,
    ReadFileTool,
    WriteFileTool,
)
from amberclaw.tools.hardware import (
    GPIOTool,
    HardwareControlTool,
    HardwareReadTool,
    HardwareScanTool,
)
from amberclaw.tools.memory_tools import (
    ForgetTool,
    RecallTool,
    RememberTool,
    SessionSearchTool,
    SummarizeSessionTool,
)
from amberclaw.tools.reasoning import CouncilTool, MythosTool
from amberclaw.tools.registry import BaseTool, registry
from amberclaw.tools.subagent_tools import SpawnTool
from amberclaw.tools.web_tools import WebFetchTool, WebSearchTool


def get_default_toolset(
    sandbox: FilesystemSandbox | None = None,
    provider: LLMProvider | None = None,
    subagent_manager: "SubagentManager | None" = None,
) -> list[BaseTool[...]]:
    """Returns the default set of tools for a production agent."""

    return [
        # Filesystem
        ReadFileTool(sandbox=sandbox),
        WriteFileTool(sandbox=sandbox),
        ListDirTool(sandbox=sandbox),
        # Reasoning
        CouncilTool(provider=provider),
        MythosTool(provider=provider),
        # Web
        WebSearchTool(),
        WebFetchTool(),
        # Data
        DataCleanTool(provider=provider),
        # Hardware & Edge
        HardwareControlTool(),
        HardwareReadTool(),
        HardwareScanTool(),
        GPIOTool(),
        # Agents
        SpawnTool(manager=subagent_manager),
        # Memory
        RememberTool(),
        RecallTool(),
        ForgetTool(),
        SessionSearchTool(),
        SummarizeSessionTool(),
    ]


def register_default_tools() -> None:
    """Register all default tools in the global registry."""
    for tool in get_default_toolset():
        registry.register(tool)
