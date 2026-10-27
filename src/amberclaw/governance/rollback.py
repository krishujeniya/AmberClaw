"""Compensating actions and rollback manager for governed agent operations."""

import time
import uuid
from collections.abc import Callable
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RollbackStatus(StrEnum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class RollbackStep(BaseModel):
    """A discrete compensatory action step."""

    step_id: str = Field(default_factory=lambda: f"RBS-{uuid.uuid4().hex[:6].upper()}")
    action_type: str = Field(..., description="Type of rollback operation (e.g. file_restore, git_revert, state_reset).")
    target: str = Field(..., description="Target entity or path being restored.")
    parameters: dict[str, Any] = Field(default_factory=dict)
    status: RollbackStatus = RollbackStatus.PENDING
    error: str | None = None


class RollbackPlan(BaseModel):
    """An ordered series of compensatory actions reversing a governed operation."""

    plan_id: str = Field(default_factory=lambda: f"RBP-{uuid.uuid4().hex[:8].upper()}")
    action_id: str = Field(..., description="Original governed action ID being rolled back.")
    created_at: float = Field(default_factory=time.time)
    steps: list[RollbackStep] = Field(default_factory=list)
    status: RollbackStatus = RollbackStatus.PENDING


class GovernanceRollbackManager:
    """Registers and executes reversible checkpoints and compensatory actions."""

    def __init__(self) -> None:
        self._plans: dict[str, RollbackPlan] = {}
        self._handlers: dict[str, Callable[[RollbackStep], bool]] = {}
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        def handle_generic_noop(_step: RollbackStep) -> bool:
            return True

        self._handlers["noop"] = handle_generic_noop
        self._handlers["file_restore"] = handle_generic_noop
        self._handlers["state_reset"] = handle_generic_noop
        self._handlers["git_revert"] = handle_generic_noop

    def register_handler(self, action_type: str, handler: Callable[[RollbackStep], bool]) -> None:
        """Register an execution handler for a specific rollback action type."""
        self._handlers[action_type] = handler

    def create_plan(self, action_id: str) -> RollbackPlan:
        """Create a new empty rollback plan for an action."""
        plan = RollbackPlan(action_id=action_id)
        self._plans[plan.plan_id] = plan
        return plan

    def add_step(
        self,
        plan_id: str,
        action_type: str,
        target: str,
        parameters: dict[str, Any] | None = None,
    ) -> RollbackStep:
        """Append a compensatory step to a plan."""
        plan = self._plans.get(plan_id)
        if not plan:
            raise KeyError(f"Rollback plan {plan_id} not found.")

        step = RollbackStep(
            action_type=action_type,
            target=target,
            parameters=parameters or {},
        )
        plan.steps.append(step)
        return step

    def execute_plan(self, plan_id: str) -> RollbackPlan:
        """Execute all steps in a rollback plan in sequential order."""
        plan = self._plans.get(plan_id)
        if not plan:
            raise KeyError(f"Rollback plan {plan_id} not found.")

        plan.status = RollbackStatus.EXECUTING
        has_failure = False

        for step in plan.steps:
            handler = self._handlers.get(step.action_type, self._handlers["noop"])
            step.status = RollbackStatus.EXECUTING
            try:
                success = handler(step)
                if success:
                    step.status = RollbackStatus.COMPLETED
                else:
                    step.status = RollbackStatus.FAILED
                    step.error = "Handler returned False"
                    has_failure = True
            except Exception as e:
                step.status = RollbackStatus.FAILED
                step.error = str(e)
                has_failure = True

        plan.status = RollbackStatus.FAILED if has_failure else RollbackStatus.COMPLETED
        return plan

    def get_plan(self, plan_id: str) -> RollbackPlan | None:
        """Retrieve plan by ID."""
        return self._plans.get(plan_id)
