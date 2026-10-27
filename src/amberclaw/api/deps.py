"""Dependency injection providers for FastAPI route handlers."""

from functools import lru_cache

from amberclaw.services.agent_service import AgentService
from amberclaw.services.budget_service import BudgetService
from amberclaw.services.chat_service import ChatService
from amberclaw.services.memory_service import MemoryService
from amberclaw.services.skill_service import SkillService
from amberclaw.services.ticket_service import TicketService


@lru_cache(maxsize=1)
def get_chat_service() -> ChatService:
    """Provide singleton instance of ChatService."""
    return ChatService()


@lru_cache(maxsize=1)
def get_agent_service() -> AgentService:
    """Provide singleton instance of AgentService."""
    return AgentService()


@lru_cache(maxsize=1)
def get_ticket_service() -> TicketService:
    """Provide singleton instance of TicketService."""
    return TicketService()


@lru_cache(maxsize=1)
def get_memory_service() -> MemoryService:
    """Provide singleton instance of MemoryService."""
    return MemoryService()


@lru_cache(maxsize=1)
def get_budget_service() -> BudgetService:
    """Provide singleton instance of BudgetService."""
    return BudgetService()


@lru_cache(maxsize=1)
def get_skill_service() -> SkillService:
    """Provide singleton instance of SkillService."""
    return SkillService()


__all__ = [
    "get_agent_service",
    "get_budget_service",
    "get_chat_service",
    "get_memory_service",
    "get_skill_service",
    "get_ticket_service",
]
