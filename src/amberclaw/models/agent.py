"""Domain model representing an AmberClaw AI Agent entity."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentModel(BaseModel):
    """Configuration and state entity for an AI agent instance."""

    id: str = Field(..., description="Unique agent identifier.")
    name: str = Field(..., description="Human-readable agent name.")
    role: str = Field(default="assistant", description="Agent functional role.")
    system_prompt: str | None = Field(default=None, description="Base system instructions.")
    model_name: str = Field(default="gpt-4o", description="Default LLM model identifier.")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Model sampling temperature.")
    tools: list[str] = Field(default_factory=list, description="Enabled tool names.")
    is_active: bool = Field(default=True, description="Whether agent is active and callable.")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)
