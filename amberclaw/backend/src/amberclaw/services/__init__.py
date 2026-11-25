"""AmberClaw service layer coordinating domain operations between API routes and subsystems."""

from pydantic import BaseModel, Field

from amberclaw.services.agent_service import AgentService
from amberclaw.services.budget_service import BudgetService
from amberclaw.services.chat_service import ChatService
from amberclaw.services.memory_service import MemoryService
from amberclaw.services.skill_service import SkillService
from amberclaw.services.ticket_service import TicketService


class ServicesModuleConfig(BaseModel):
    """Configuration for the amberclaw.services module."""

    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = [
    "AgentService",
    "BudgetService",
    "ChatService",
    "MemoryService",
    "ServicesModuleConfig",
    "SkillService",
    "TicketService",
]
