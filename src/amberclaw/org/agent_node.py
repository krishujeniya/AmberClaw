"""Agent node representation within an organizational chart."""

from typing import Any

from pydantic import BaseModel, Field

from amberclaw.org.permissions import OrgPermission, OrgRole


class AgentNode(BaseModel):
    """Represents an agent entity with hierarchical role and organizational boundaries."""

    id: str
    name: str
    role: OrgRole = OrgRole.SPECIALIST_AGENT
    department: str = "engineering"
    manager_id: str | None = None
    subordinate_ids: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    custom_permissions: set[OrgPermission] = Field(default_factory=set)
    budget_limit_usd: float = Field(default=100.0, ge=0.0)
    tenant_id: str = "default"
    metadata: dict[str, Any] = Field(default_factory=dict)

    def add_subordinate(self, agent_id: str) -> None:
        """Add subordinate ID if not already present."""
        if agent_id not in self.subordinate_ids and agent_id != self.id:
            self.subordinate_ids.append(agent_id)

    def remove_subordinate(self, agent_id: str) -> None:
        """Remove subordinate ID."""
        if agent_id in self.subordinate_ids:
            self.subordinate_ids.remove(agent_id)

    def has_capability(self, capability: str) -> bool:
        """Check if agent provides a specific capability."""
        return capability in self.capabilities
