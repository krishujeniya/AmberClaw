"""Unit tests for AmberClaw core domain models."""

from amberclaw.models import (
    AgentModel,
    CompanyModel,
    Conversation,
    GoalModel,
    GoalStatus,
    Message,
    MessageRole,
    TicketModel,
    TicketPriority,
    TicketStatus,
    ToolCall,
    ToolResult,
    WorkspaceModel,
)


def test_agent_model_instantiation():
    agent = AgentModel(
        id="agent-001",
        name="SecurityAuditor",
        role="security",
        system_prompt="Audit source code for vulnerabilities.",
        model_name="claude-3-5-sonnet-20241022",
        temperature=0.2,
        tools=["read_file", "run_linter"],
    )
    assert agent.id == "agent-001"
    assert agent.name == "SecurityAuditor"
    assert agent.is_active is True
    expected_tools_count = 2
    assert len(agent.tools) == expected_tools_count


def test_company_and_workspace_models():
    company = CompanyModel(
        id="comp-10",
        name="Acme Corp",
        domain="acme.internal",
        departments=["Engineering", "Operations"],
    )
    assert company.id == "comp-10"
    assert "Engineering" in company.departments

    workspace = WorkspaceModel(
        id="ws-100",
        name="Backend Core",
        root_path="/workspaces/backend",
        company_id=company.id,
        is_isolated=True,
    )
    assert workspace.company_id == "comp-10"
    assert workspace.is_isolated is True


def test_goal_model():
    expected_milestones_count = 3
    expected_progress = 85.5
    goal = GoalModel(
        id="goal-42",
        title="Achieve 100% test coverage",
        description="Write unit and integration tests across all packages.",
        status=GoalStatus.IN_PROGRESS,
        priority=1,
        progress_percent=expected_progress,
        milestones=["Agent subsystems", "Skills framework", "Sandbox isolation"],
    )
    assert goal.status == GoalStatus.IN_PROGRESS
    assert goal.progress_percent == expected_progress
    assert len(goal.milestones) == expected_milestones_count


def test_ticket_model():
    ticket = TicketModel(
        id="ticket-99",
        title="Approve production deployment",
        description="Deploying release v2.0.0 to AWS cluster",
        status=TicketStatus.PENDING_APPROVAL,
        priority=TicketPriority.CRITICAL,
        requester_id="agent-001",
        tool_call_payload={"action": "deploy", "target": "prod"},
    )
    assert ticket.priority == TicketPriority.CRITICAL
    assert ticket.status == TicketStatus.PENDING_APPROVAL
    assert ticket.tool_call_payload["action"] == "deploy"


def test_message_and_conversation_models():
    tool_call = ToolCall(
        id="call-1",
        function={"name": "grep_search", "arguments": '{"query": "def test"}'},
    )
    msg_user = Message(role=MessageRole.USER, content="Run security scan")
    msg_assistant = Message(
        role=MessageRole.ASSISTANT,
        content=None,
        tool_calls=[tool_call],
    )
    tool_res = ToolResult(tool_call_id="call-1", output="Found 4 matches")
    msg_tool = Message(
        role=MessageRole.TOOL,
        content=tool_res.output,
        tool_call_id=tool_res.tool_call_id,
    )

    conv = Conversation(
        id="conv-1",
        messages=[msg_user, msg_assistant, msg_tool],
    )
    expected_messages_count = 3
    assert len(conv.messages) == expected_messages_count
    assert conv.messages[0].role == MessageRole.USER
    assert conv.messages[1].tool_calls[0].id == "call-1"
    assert conv.messages[2].content == "Found 4 matches"
