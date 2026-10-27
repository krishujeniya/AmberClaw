"""Declarative Blueprint schema models for AmberClaw configurations."""

from typing import Any

from pydantic import BaseModel, Field


class AgentBlueprintConfig(BaseModel):
    """Agent runtime settings defined within a blueprint."""

    model_name: str = Field(default="gpt-4o", description="Default model name.")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature.")
    system_prompt: str | None = Field(default=None, description="Custom system prompt directive.")
    max_turns: int = Field(default=50, ge=1, le=1000, description="Maximum agent conversation turns.")
    memory_nudge_enabled: bool = Field(default=True, description="Enable memory nudge heuristics.")


class SecurityBlueprintConfig(BaseModel):
    """Security and sandbox isolation policies defined within a blueprint."""

    sandbox_type: str = Field(default="docker", description="Isolation sandbox type (e.g. docker, local, wasm, modal).")
    allow_network_egress: bool = Field(default=True, description="Whether network egress is permitted.")
    restricted_paths: list[str] = Field(
        default_factory=lambda: ["/etc", "/root", "~/.ssh"],
        description="Protected filesystem paths forbidden from tool access.",
    )
    require_human_approval_for_destructive: bool = Field(
        default=True,
        description="Enforce HITL approval tickets for high-risk operations.",
    )


class BlueprintSchema(BaseModel):
    """Complete declarative blueprint configuration for AmberClaw deployment."""

    name: str = Field(..., description="Unique blueprint profile name.")
    version: str = Field(default="1.0.0", description="Blueprint version string.")
    description: str = Field(default="", description="Description of blueprint purpose.")
    agent: AgentBlueprintConfig = Field(default_factory=AgentBlueprintConfig)
    security: SecurityBlueprintConfig = Field(default_factory=SecurityBlueprintConfig)
    skills: list[str] = Field(default_factory=list, description="List of enabled skill names.")
    channels: list[str] = Field(default_factory=list, description="List of enabled channel names.")
    metadata: dict[str, Any] = Field(default_factory=dict)
