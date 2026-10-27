"""AmberClaw subagent orchestration and execution module."""

from pydantic import BaseModel, Field

from amberclaw.subagent.agent import (
    SubagentResult,
    SubagentStatus,
    SubagentTask,
    SubagentWorker,
)
from amberclaw.subagent.isolation import (
    IsolationPolicy,
    SubagentIsolationContext,
)
from amberclaw.subagent.pool import SubagentPool
from amberclaw.subagent.rpc import (
    RPCMessage,
    RPCMessageType,
    SubagentRPCChannel,
)


class SubagentModuleConfig(BaseModel):
    """Configuration for the amberclaw.subagent module."""

    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")
    default_max_concurrency: int = Field(default=5, ge=1)
    default_timeout_seconds: float = Field(default=300.0, ge=1.0)


__all__ = [
    "IsolationPolicy",
    "RPCMessage",
    "RPCMessageType",
    "SubagentIsolationContext",
    "SubagentModuleConfig",
    "SubagentPool",
    "SubagentRPCChannel",
    "SubagentResult",
    "SubagentStatus",
    "SubagentTask",
    "SubagentWorker",
]
