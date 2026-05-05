"""
AmberClaw Toolsets Configuration
"""
from typing import List
from amberclaw.tools.registry import BaseTool, registry
from amberclaw.security.sandbox import LocalSandbox
from amberclaw.tools.filesystem import ReadFileTool, WriteFileTool, ListDirTool
from amberclaw.tools.reasoning import CouncilTool, MythosTool
from amberclaw.tools.web_tools import WebSearchTool, WebFetchTool
from amberclaw.tools.subagent_tools import SpawnTool


def get_default_toolset() -> List[BaseTool]:
    """Returns the default set of tools for a production agent."""
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

        # Agents
        SpawnTool(),
    ]


def register_default_tools():
    """Register all default tools in the global registry."""
    for tool in get_default_toolset():
        registry.register(tool)
