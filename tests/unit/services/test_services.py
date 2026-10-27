# ruff: noqa: PLR2004
"""Unit tests for AmberClaw Service Layer and API Dependency Injection."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from amberclaw.api.deps import (
    get_agent_service,
    get_budget_service,
    get_chat_service,
    get_memory_service,
    get_skill_service,
    get_ticket_service,
)
from amberclaw.api.v1.budget import TenantQuotaManager
from amberclaw.governance.tickets import TicketPriority, TicketStatus, TicketSystem
from amberclaw.memory.session_db import SessionDB
from amberclaw.schemas.agent import AgentProfile
from amberclaw.services.agent_service import AgentService
from amberclaw.services.budget_service import BudgetService
from amberclaw.services.chat_service import ChatService
from amberclaw.services.memory_service import MemoryService
from amberclaw.services.skill_service import SkillService
from amberclaw.services.ticket_service import TicketService
from amberclaw.skills.registry import SkillRegistry
from amberclaw.skills.skill import SkillDefinition, SkillMetadata
from amberclaw.storage.persistence import JSONStateStore

# ==============================================================================
# ChatService Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_chat_service_generate_response(tmp_path: Path):
    store = JSONStateStore(tmp_path / "agents.json", AgentProfile)
    mock_router = MagicMock()
    mock_router.generate = AsyncMock(return_value="Hello, human!")

    service = ChatService(llm_router=mock_router, agent_store=store)
    reply, model = await service.generate_response(
        message="Hi",
        model="gpt-4o",
        system_prompt="Be friendly.",
    )
    assert reply == "Hello, human!"
    assert model == "gpt-4o"
    mock_router.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_chat_service_with_agent(tmp_path: Path):
    store = JSONStateStore(tmp_path / "agents.json", AgentProfile)
    agent = AgentProfile(
        agent_id="bot-1",
        name="SecurityBot",
        role="Auditor",
        model_name="claude-3-5-sonnet",
    )
    store.set("bot-1", agent)

    mock_router = MagicMock()
    mock_router.generate = AsyncMock(return_value="System secure.")

    service = ChatService(llm_router=mock_router, agent_store=store)
    reply, model = await service.generate_response(
        message="Status?",
        agent_id="bot-1",
    )
    assert reply == "System secure."
    assert model == "claude-3-5-sonnet"


@pytest.mark.asyncio
async def test_chat_service_agent_not_found(tmp_path: Path):
    store = JSONStateStore(tmp_path / "agents.json", AgentProfile)
    service = ChatService(agent_store=store)
    with pytest.raises(KeyError, match="Agent 'ghost' not found"):
        await service.generate_response(message="Hi", agent_id="ghost")


@pytest.mark.asyncio
async def test_chat_service_stream_response(tmp_path: Path):
    store = JSONStateStore(tmp_path / "agents.json", AgentProfile)
    mock_router = MagicMock()

    async def _mock_stream(**_kwargs):
        for token in ["Hello", " ", "world"]:
            yield token

    mock_router.generate_stream = _mock_stream
    service = ChatService(llm_router=mock_router, agent_store=store)

    frames = [frame async for frame in service.stream_response(message="Hello")]
    assert len(frames) == 4  # 3 token frames + 1 done frame
    assert any("Hello" in f for f in frames)
    assert any("[DONE]" in f or "total_tokens" in f for f in frames)


# ==============================================================================
# AgentService Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_agent_service_lifecycle(tmp_path: Path):
    store = JSONStateStore(tmp_path / "agents.json", AgentProfile)
    mock_router = MagicMock()
    mock_router.generate = AsyncMock(return_value="Agent active.")

    service = AgentService(agent_store=store, llm_router=mock_router)

    agent_a = AgentProfile(
        agent_id="agent-a",
        name="Alpha",
        role="Lead",
        model_name="gpt-4o",
    )
    agent_b = AgentProfile(
        agent_id="agent-b",
        name="Beta",
        role="Worker",
        model_name="gpt-4o-mini",
    )

    # Spawn
    service.spawn_agent(agent_a)
    service.spawn_agent(agent_b)

    with pytest.raises(ValueError, match="already active"):
        service.spawn_agent(agent_a)

    # List & Get
    agents = service.list_agents(order_by="name")
    assert len(agents) == 2
    assert agents[0].name == "Alpha"

    retrieved = service.get_agent("agent-a")
    assert retrieved is not None
    assert retrieved.name == "Alpha"

    # Chat
    reply, aid = await service.chat_with_agent("agent-a", "Report")
    assert reply == "Agent active."
    assert aid == "agent-a"

    # Delete
    assert service.delete_agent("agent-a") is True
    assert service.get_agent("agent-a") is None
    assert service.delete_agent("non-existent") is False


# ==============================================================================
# TicketService Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_ticket_service_lifecycle(tmp_path: Path):
    system = TicketSystem(store_path=tmp_path / "tickets.json")
    mock_audit = MagicMock()

    service = TicketService(ticket_system=system, audit_logger=mock_audit)

    ticket = await service.create_ticket(
        requester_id="user-42",
        description="Deploy to production cluster",
        priority=TicketPriority.HIGH,
        context={"cluster": "us-east-1"},
    )
    assert ticket.id is not None
    assert ticket.status == TicketStatus.PENDING
    mock_audit.log_event.assert_called()

    # List
    pending = service.get_pending_tickets()
    assert len(pending) == 1
    assert pending[0].id == ticket.id

    # Resolve
    resolved = await service.resolve_ticket(
        ticket_id=ticket.id,
        status=TicketStatus.APPROVED,
        reviewer_id="operator-1",
        notes="All safety checks passed",
    )
    assert resolved.status == TicketStatus.APPROVED
    assert resolved.reviewer_id == "operator-1"
    assert service.get_pending_tickets() == []


# ==============================================================================
# MemoryService Tests
# ==============================================================================


def test_memory_service(tmp_path: Path):
    db_path = tmp_path / "test_memory.db"
    session_db = SessionDB(db_path=db_path)
    service = MemoryService(session_db=session_db)

    session_db.add_turn("session-1", "user", "My secret info", user_id="u123")
    session_db.add_turn("session-1", "assistant", "Acknowledged", user_id="u123")

    export = service.export_data(session_id="session-1")
    assert export["total_turns"] == 2
    assert "checksum_sha256" in export

    deleted = service.delete_session("session-1")
    assert deleted == 2

    export_after = service.export_data(session_id="session-1")
    assert export_after["total_turns"] == 0


# ==============================================================================
# BudgetService Tests
# ==============================================================================


def test_budget_service():
    mgr = TenantQuotaManager()
    service = BudgetService(quota_manager=mgr)

    quota = service.get_quota("tenant-acme")
    assert quota.tokens_used == 0

    service.record_usage("tenant-acme", tokens=1500, cost=0.03)
    updated = service.get_quota("tenant-acme")
    assert updated.tokens_used == 1500
    assert updated.spent_usd == 0.03
    assert updated.requests_count == 1

    service.update_budget("tenant-acme", max_tokens=500000, max_budget_usd=100.0)
    final_quota = service.get_quota("tenant-acme")
    assert final_quota.max_tokens_limit == 500000
    assert final_quota.max_budget_usd == 100.0


# ==============================================================================
# SkillService Tests
# ==============================================================================


def test_skill_service():
    registry = SkillRegistry()
    skill = SkillDefinition(
        name="web_search",
        metadata=SkillMetadata(name="web_search", description="Search the web"),
        source_code="def run(): pass",
    )
    registry.register(skill)

    service = SkillService(registry=registry)
    assert len(service.list_skills()) == 1
    assert service.get_skill("web_search") is not None

    service.set_skill_enabled("web_search", False)
    assert service.get_skill("web_search").is_enabled is False

    service.set_skill_enabled("web_search", True)
    assert service.get_skill("web_search").is_enabled is True

    service.record_usage("web_search", duration_ms=120.5, success=True)
    metric = service.get_metrics("web_search")
    assert metric is not None
    assert metric.invocations == 1


# ==============================================================================
# API Dependency Injection Tests
# ==============================================================================


def test_api_deps():
    assert get_chat_service() is not None
    assert get_agent_service() is not None
    assert get_ticket_service() is not None
    assert get_memory_service() is not None
    assert get_budget_service() is not None
    assert get_skill_service() is not None
