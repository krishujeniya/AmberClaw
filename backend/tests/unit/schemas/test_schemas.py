# ruff: noqa: PLR2004, S104
"""Unit tests for AmberClaw schemas: common, message, config, and agent."""

from amberclaw.schemas.agent import AgentProfile, SubagentTask
from amberclaw.schemas.common import PaginatedResponse, PaginationParams, StatusResponse
from amberclaw.schemas.config import GatewayConfigSchema, SecurityConfigSchema
from amberclaw.schemas.message import (
    ChatMessageSchema,
    InboundMessageSchema,
    MessageRole,
    OutboundMessageSchema,
)


def test_status_response_schema():
    resp = StatusResponse(status="healthy", details={"uptime_seconds": 3600})
    assert resp.status == "healthy"
    assert resp.details["uptime_seconds"] == 3600
    assert resp.timestamp is not None


def test_pagination_schemas():
    params = PaginationParams(page=2, per_page=10)
    assert params.page == 2
    assert params.per_page == 10

    page_data = PaginatedResponse[str](
        items=["agent_1", "agent_2"],
        total=2,
        page=1,
        per_page=10,
        total_pages=1,
    )
    assert page_data.total == 2
    assert len(page_data.items) == 2


def test_chat_message_schemas():
    msg = ChatMessageSchema(
        role=MessageRole.USER,
        content="What is the current system load?",
    )
    assert msg.role == MessageRole.USER
    assert msg.content == "What is the current system load?"

    inbound = InboundMessageSchema(
        channel="telegram",
        sender_id="user_123",
        chat_id="chat_456",
        text="Hello agent",
    )
    assert inbound.channel == "telegram"
    assert inbound.sender_id == "user_123"

    outbound = OutboundMessageSchema(
        recipient_id="user_123",
        channel="telegram",
        text="Hello human",
    )
    assert outbound.recipient_id == "user_123"
    assert outbound.channel == "telegram"


def test_runtime_config_schemas():
    gw = GatewayConfigSchema(host="0.0.0.0", port=9000)
    assert gw.host == "0.0.0.0"
    assert gw.port == 9000

    sec = SecurityConfigSchema(sandbox_type="wasm", require_mfa=True)
    assert sec.sandbox_type == "wasm"
    assert sec.require_mfa is True


def test_agent_schemas():
    task = SubagentTask(description="Perform code review")
    assert task.task_id.startswith("task_")
    assert task.status == "pending"

    profile = AgentProfile(name="AuditBot", role="Security Auditor")
    assert profile.name == "AuditBot"
    assert profile.model_provider == "openai"
    assert profile.budget_limit == 5.0
