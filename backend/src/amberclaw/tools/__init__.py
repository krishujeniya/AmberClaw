"""AmberClaw unified agent toolsets and extensible tool registry."""

from pydantic import BaseModel, Field

from amberclaw.tools.meta_tools import InspectToolSchemaTool, ListToolsTool
from amberclaw.tools.registry import BaseTool, ToolRegistry
from amberclaw.tools.rl_tools import (
    RecordTrajectoryStepTool,
    RLBufferStatsTool,
    RLDiagnosticsTool,
)


class ToolsModuleConfig(BaseModel):
    """Configuration for the amberclaw.tools module."""

    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = [
    "BaseTool",
    "InspectToolSchemaTool",
    "ListToolsTool",
    "RLBufferStatsTool",
    "RLDiagnosticsTool",
    "RecordTrajectoryStepTool",
    "ToolRegistry",
    "ToolsModuleConfig",
]
