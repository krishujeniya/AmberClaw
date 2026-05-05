from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid

class SubagentTask(BaseModel):
    """
    Represents a specific unit of work assigned to a subagent.
    """
    task_id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    description: str = Field(..., description="Instructions for the subagent.")
    dependencies: List[str] = Field(default_factory=list, description="List of task IDs that must complete first.")
    status: str = Field(default="pending", description="pending, running, completed, failed")
    result: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AgentProfile(BaseModel):
    """
    Core identity and configuration for an AmberClaw Agent.
    """
    agent_id: str = Field(default_factory=lambda: f"agent_{uuid.uuid4().hex[:8]}")
    name: str = Field(..., description="Display name of the agent.")
    role: str = Field(..., description="System prompt role or persona.")
    model_provider: str = Field(default="openai", description="Default LLM provider to route requests to.")
    model_name: str = Field(default="gpt-4o", description="Specific model identifier.")
    allowed_tools: List[str] = Field(default_factory=list, description="Tools this agent is permitted to use.")
    budget_limit: float = Field(default=5.0, description="Max spend limit in USD before requiring approval.")
    
    # OS tracking
    is_active: bool = Field(default=True)
    active_tasks: List[SubagentTask] = Field(default_factory=list)
