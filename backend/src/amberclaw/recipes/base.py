# ruff: noqa: S101
"""Base Recipe Models and Interfaces for Private Operations (CL-021)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RecipeStatus(StrEnum):
    COMPLETED = "completed"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class RecipeManifest(BaseModel):
    """Declarative specification for a versioned private operations recipe."""

    recipe_id: str
    version: str = "1.0.0"
    name: str
    description: str
    required_scopes: list[str] = Field(default_factory=list)
    estimated_cost_usd: float = 0.005
    requires_human_approval: bool = False
    failure_recovery_policy: str = "compensate_and_halt"
    input_parameters: dict[str, str] = Field(default_factory=dict)
    output_contract: dict[str, str] = Field(default_factory=dict)


class RecipeExecutionResult(BaseModel):
    """Structured outcome resulting from executing a private operations recipe."""

    recipe_id: str
    run_id: str = Field(default_factory=lambda: f"rcprun_{uuid.uuid4().hex[:12]}")
    status: RecipeStatus
    final_state: dict[str, Any] = Field(default_factory=dict)
    approval_ticket_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    actual_cost_usd: float = 0.0
    safety_checks_passed: bool = True
    executed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    error: str | None = None
