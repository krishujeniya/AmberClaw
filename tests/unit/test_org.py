# ruff: noqa: PLR2004
"""Unit tests for AmberClaw Org Hierarchy and Multitenancy Authorization."""

import pytest

from amberclaw.org.agent_node import AgentNode
from amberclaw.org.chart import OrgChart
from amberclaw.org.permissions import OrgPermission, OrgPolicy, OrgRole


def test_agent_node_basics():
    node = AgentNode(
        id="agent_lead_1",
        name="Engineering Lead",
        role=OrgRole.DEPARTMENT_LEAD,
        department="engineering",
        capabilities=["code_review", "deploy"],
        budget_limit_usd=500.0,
    )
    assert node.role == OrgRole.DEPARTMENT_LEAD
    assert node.has_capability("code_review")
    assert not node.has_capability("marketing")

    node.add_subordinate("agent_eng_1")
    assert "agent_eng_1" in node.subordinate_ids

    # Duplicate should not be added
    node.add_subordinate("agent_eng_1")
    assert len(node.subordinate_ids) == 1

    node.remove_subordinate("agent_eng_1")
    assert "agent_eng_1" not in node.subordinate_ids


def test_org_chart_cycle_detection():
    chart = OrgChart()

    root = AgentNode(id="ceo", name="CEO", role=OrgRole.ADMIN, department="executive")
    chart.add_agent(root)

    # Self reference
    with pytest.raises(ValueError, match="cannot be its own manager"):
        chart.add_agent(AgentNode(id="self_mgr", name="Self", manager_id="self_mgr"))

    # Multi-node cycle
    node_a = AgentNode(id="node_a", name="A", manager_id="ceo")
    chart.add_agent(node_a)

    node_b = AgentNode(id="node_b", name="B", manager_id="node_a")
    chart.add_agent(node_b)

    # Attempting to make node_a report to node_b creates cycle
    with pytest.raises(ValueError, match="creates a cycle"):
        chart.add_agent(AgentNode(id="node_a", name="A", manager_id="node_b"))


def test_org_chart_hierarchy_and_subordinates():
    chart = OrgChart()

    lead = AgentNode(id="lead_1", name="Lead", role=OrgRole.DEPARTMENT_LEAD, department="eng")
    staff = AgentNode(id="staff_1", name="Staff", role=OrgRole.STAFF_AGENT, department="eng", manager_id="lead_1")
    intern = AgentNode(id="intern_1", name="Intern", role=OrgRole.INTERN_AGENT, department="eng", manager_id="staff_1")

    chart.add_agent(lead)
    chart.add_agent(staff)
    chart.add_agent(intern)

    # Direct subordinates
    direct_subs = chart.get_subordinates("lead_1", recursive=False)
    assert len(direct_subs) == 1
    assert direct_subs[0].id == "staff_1"

    # Recursive subordinates
    rec_subs = chart.get_subordinates("lead_1", recursive=True)
    assert len(rec_subs) == 2
    sub_ids = {s.id for s in rec_subs}
    assert sub_ids == {"staff_1", "intern_1"}

    # Escalation path
    escalation = chart.get_escalation_path("intern_1")
    assert len(escalation) == 2
    assert escalation[0].id == "staff_1"
    assert escalation[1].id == "lead_1"


def test_org_delegation_policies():
    chart = OrgChart(policy=OrgPolicy(strict_hierarchy_enforcement=True))

    admin = AgentNode(id="admin_1", name="Admin", role=OrgRole.ADMIN, department="ops")
    eng_lead = AgentNode(id="eng_lead", name="Eng Lead", role=OrgRole.DEPARTMENT_LEAD, department="engineering")
    eng_dev = AgentNode(id="eng_dev", name="Developer", role=OrgRole.SPECIALIST_AGENT, department="engineering")
    eng_intern = AgentNode(id="eng_intern", name="Intern", role=OrgRole.INTERN_AGENT, department="engineering")
    sales_rep = AgentNode(id="sales_rep", name="Sales Rep", role=OrgRole.SPECIALIST_AGENT, department="sales")

    chart.add_agent(admin)
    chart.add_agent(eng_lead)
    chart.add_agent(eng_dev)
    chart.add_agent(eng_intern)
    chart.add_agent(sales_rep)

    # 1. Lead delegates to Dev in same dept -> Allowed
    assert chart.can_delegate("eng_lead", "eng_dev") is True

    # 2. Intern attempts to delegate -> Blocked (Intern has no DELEGATE permission)
    assert chart.can_delegate("eng_intern", "eng_dev") is False

    # 3. Dev attempts to delegate up to Lead with strict hierarchy -> Blocked
    assert chart.can_delegate("eng_dev", "eng_lead") is False

    # 4. Dev delegates across departments (eng -> sales) without CROSS_DEPT_CALL -> Blocked
    assert chart.can_delegate("eng_dev", "sales_rep") is False

    # 5. Admin delegates anywhere -> Allowed (Admin has CROSS_DEPT_CALL & top level)
    assert chart.can_delegate("admin_1", "sales_rep") is True

    # 6. Dev with custom CROSS_DEPT_CALL permission -> Allowed
    eng_dev_cross = AgentNode(
        id="eng_dev_cross",
        name="Dev Cross",
        role=OrgRole.STAFF_AGENT,
        department="engineering",
        custom_permissions={OrgPermission.CROSS_DEPT_CALL},
    )
    chart.add_agent(eng_dev_cross)
    assert chart.can_delegate("eng_dev_cross", "sales_rep") is True


def test_tenant_boundary_isolation():
    chart = OrgChart()

    tenant_a_admin = AgentNode(id="admin_a", name="Admin A", role=OrgRole.ADMIN, tenant_id="tenant_a")
    tenant_b_dev = AgentNode(id="dev_b", name="Dev B", role=OrgRole.SPECIALIST_AGENT, tenant_id="tenant_b")

    chart.add_agent(tenant_a_admin)
    chart.add_agent(tenant_b_dev)

    # Cross-tenant delegation must be strictly blocked
    assert chart.can_delegate("admin_a", "dev_b") is False


def test_org_chart_serialization_roundtrip():
    chart = OrgChart()
    lead = AgentNode(id="lead_1", name="Lead", role=OrgRole.DEPARTMENT_LEAD, department="ops")
    spec = AgentNode(id="spec_1", name="Specialist", role=OrgRole.SPECIALIST_AGENT, department="ops", manager_id="lead_1")
    chart.add_agent(lead)
    chart.add_agent(spec)

    data = chart.to_dict()
    restored = OrgChart.from_dict(data)

    assert len(restored.nodes) == 2
    assert restored.get_manager("spec_1").id == "lead_1"
    assert restored.can_delegate("lead_1", "spec_1") is True
