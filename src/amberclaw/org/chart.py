"""Organizational Chart manager for multi-agent hierarchies."""

from typing import Any

from pydantic import BaseModel, Field

from amberclaw.org.agent_node import AgentNode
from amberclaw.org.permissions import OrgPolicy


class OrgChart(BaseModel):
    """Hierarchical graph representing organizational agent relationships and boundaries."""

    nodes: dict[str, AgentNode] = Field(default_factory=dict)
    policy: OrgPolicy = Field(default_factory=OrgPolicy)

    def add_agent(self, agent: AgentNode) -> None:
        """Add or update an agent node in the org chart."""
        # Cycle detection
        if agent.manager_id:
            if agent.manager_id == agent.id:
                raise ValueError(f"Agent {agent.id} cannot be its own manager.")
            if self._creates_cycle(agent.id, agent.manager_id):
                raise ValueError(f"Adding manager {agent.manager_id} to agent {agent.id} creates a cycle.")

        self.nodes[agent.id] = agent

        # Link to manager's subordinates
        if agent.manager_id and agent.manager_id in self.nodes:
            self.nodes[agent.manager_id].add_subordinate(agent.id)

    def _creates_cycle(self, node_id: str, manager_id: str) -> bool:
        """Check if assigning manager_id to node_id produces a loop."""
        visited = {node_id}
        current_id: str | None = manager_id

        while current_id is not None:
            if current_id in visited:
                return True
            visited.add(current_id)
            manager_node = self.nodes.get(current_id)
            current_id = manager_node.manager_id if manager_node else None

        return False

    def remove_agent(self, agent_id: str) -> None:
        """Remove an agent from the org chart and re-link relationships."""
        if agent_id not in self.nodes:
            return

        target = self.nodes.pop(agent_id)

        # Unlink from manager
        if target.manager_id and target.manager_id in self.nodes:
            self.nodes[target.manager_id].remove_subordinate(agent_id)

        # Reassign or orphan subordinates
        for sub_id in target.subordinate_ids:
            if sub_id in self.nodes:
                self.nodes[sub_id].manager_id = target.manager_id
                if target.manager_id and target.manager_id in self.nodes:
                    self.nodes[target.manager_id].add_subordinate(sub_id)

    def get_agent(self, agent_id: str) -> AgentNode | None:
        """Retrieve an agent by ID."""
        return self.nodes.get(agent_id)

    def get_manager(self, agent_id: str) -> AgentNode | None:
        """Retrieve direct manager of an agent."""
        agent = self.get_agent(agent_id)
        if not agent or not agent.manager_id:
            return None
        return self.nodes.get(agent.manager_id)

    def get_subordinates(self, agent_id: str, recursive: bool = False) -> list[AgentNode]:
        """Retrieve subordinates of an agent."""
        agent = self.get_agent(agent_id)
        if not agent:
            return []

        direct = [self.nodes[sid] for sid in agent.subordinate_ids if sid in self.nodes]
        if not recursive:
            return direct

        results: list[AgentNode] = []
        queue = list(direct)
        visited = {agent_id}

        while queue:
            curr = queue.pop(0)
            if curr.id not in visited:
                visited.add(curr.id)
                results.append(curr)
                queue.extend(
                    self.nodes[sid] for sid in curr.subordinate_ids if sid in self.nodes and sid not in visited
                )

        return results

    def get_department_agents(self, department: str, tenant_id: str = "default") -> list[AgentNode]:
        """Retrieve all agents belonging to a department within a tenant."""
        return [
            node
            for node in self.nodes.values()
            if node.department == department and node.tenant_id == tenant_id
        ]

    def can_delegate(self, from_id: str, to_id: str) -> bool:
        """Evaluate if from_id can delegate a task to to_id."""
        from_agent = self.get_agent(from_id)
        to_agent = self.get_agent(to_id)

        if not from_agent or not to_agent:
            return False

        # Tenant isolation
        if from_agent.tenant_id != to_agent.tenant_id:
            return False

        same_dept = from_agent.department == to_agent.department
        return self.policy.can_delegate(
            from_role=from_agent.role,
            to_role=to_agent.role,
            same_department=same_dept,
            from_custom_perms=from_agent.custom_permissions,
        )

    def get_escalation_path(self, agent_id: str) -> list[AgentNode]:
        """Resolve hierarchy chain from agent upwards to top-level executive."""
        path: list[AgentNode] = []
        current = self.get_manager(agent_id)
        visited = {agent_id}

        while current is not None and current.id not in visited:
            visited.add(current.id)
            path.append(current)
            current = self.get_manager(current.id)

        return path

    def to_dict(self) -> dict[str, Any]:
        """Serialize org chart to dictionary."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrgChart":
        """Deserialize dictionary into OrgChart instance."""
        return cls.model_validate(data)
