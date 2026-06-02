"""
AmberClaw Toolsets Configuration
"""

from amberclaw.security.sandbox import LocalSandbox
from amberclaw.tools.filesystem import ListDirTool, ReadFileTool, WriteFileTool
from amberclaw.tools.reasoning import CouncilTool, MythosTool
from amberclaw.tools.registry import BaseTool, registry
from amberclaw.tools.subagent_tools import SpawnTool
from amberclaw.tools.web_tools import WebFetchTool, WebSearchTool
from amberclaw.tools.data_science import DataCleanTool
from amberclaw.tools.hardware import (
    HardwareControlTool,
    HardwareReadTool,
    HardwareScanTool,
    GPIOTool,
)


def get_default_toolset() -> list[BaseTool]:
    \"\"\"Returns the default set of tools for a production agent.\"\"\"
    sandbox = LocalSandbox()  # In production, this would be configured per-session
    
    return [
        # Filesystem
        ReadFileTool(sandbox=sandbox),
        WriteFileTool(sandbox=sandbox),
        ListDirTool(sandbox=sandbox),
        
        # Reasoning
        CouncilTool(),
        MythosTool(),
        
        # Web
        WebSearchTool(),
        WebFetchTool(),

        # Data
        DataCleanTool(),

        # Hardware & Edge
        HardwareControlTool(),
        HardwareReadTool(),
        HardwareScanTool(),
        GPIOTool(),

        # Agents
        SpawnTool(),
    ]


def register_default_tools():
    """Register all default tools in the global registry."""
    for tool in get_default_toolset():
        registry.register(tool)
