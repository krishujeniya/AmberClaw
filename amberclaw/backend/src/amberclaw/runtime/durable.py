# ruff: noqa: PLR0913, S608
"""Durable Run Engine and Side-Effect Safety Framework (CL-011).

Provides:
- Durable run and step state machines persisted to ACID SQLite storage.
- Idempotency key tracking and deduplication preventing duplicate external side-effects.
- Crash point recovery resuming from exact failure boundaries.
- Explicit ambiguous remote completion detection.
- Persistent human-in-the-loop approval survival across restarts.
- Reversible side-effect compensation chains.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.storage.tenant import TenantContext


class RunStatus(StrEnum):
    """Lifecycle states of a durable workflow run."""

    PENDING = "pending"
    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    AMBIGUOUS = "ambiguous"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    RECONCILED = "reconciled"


class StepStatus(StrEnum):
    """Execution states of an individual workflow step."""

    PENDING = "pending"
    IN_FLIGHT = "in_flight"
    COMPLETED = "completed"
    FAILED = "failed"
    AMBIGUOUS = "ambiguous"
    SKIPPED = "skipped"
    COMPENSATED = "compensated"


class DurableStep(BaseModel):
    """Persistent representation of a single execution step within a durable run."""

    step_id: str
    run_id: str
    step_index: int
    action_type: str
    tool_name: str | None = None
    idempotency_key: str
    status: StepStatus = StepStatus.PENDING
    args: dict[str, Any] = Field(default_factory=dict)
    result: Any | None = None
    error: str | None = None
    approval_ticket_id: str | None = None
    is_side_effect: bool = False
    compensation_action: str | None = None
    compensation_args: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DurableRun(BaseModel):
    """Persistent representation of a multi-step workflow run."""

    run_id: str
    tenant_id: str = "default"
    workflow_name: str
    status: RunStatus = RunStatus.PENDING
    initial_input: dict[str, Any] = Field(default_factory=dict)
    current_step_index: int = 0
    steps: list[DurableStep] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RecoveryReport(BaseModel):
    """Diagnostics and status summary resulting from a crash recovery analysis."""

    run_id: str
    tenant_id: str
    recovered_status: RunStatus
    total_steps: int
    completed_steps: int
    in_flight_steps_found: int
    ambiguous_steps: list[str]
    pending_approval_ticket: str | None = None
    resume_step_index: int
    can_auto_resume: bool
    summary: str


class DurableRunStore:
    """Thread-safe SQLite storage repository for durable runs and steps."""

    _instance: DurableRunStore | None = None

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @classmethod
    def get_instance(cls, db_path: Path | str | None = None) -> DurableRunStore:
        """Get or initialize singleton instance."""
        if cls._instance is None:
            default_path = Path.home() / ".amberclaw" / "durable_runs.db"
            cls._instance = cls(db_path or default_path)
        return cls._instance

    def create_run(
        self,
        tenant_id: str,
        workflow_name: str,
        initial_input: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> DurableRun:
        """Helper to create and persist a new durable run."""
        run = DurableRun(
            run_id=run_id or str(uuid.uuid4()),
            tenant_id=tenant_id,
            workflow_name=workflow_name,
            initial_input=initial_input or {},
            metadata=metadata or {},
        )
        self.save_run(run)
        return run

    def create_step(
        self,
        run_id: str,
        step_index: int,
        action_type: str,
        idempotency_key: str,
        is_side_effect: bool = False,
        tool_name: str | None = None,
        args: dict[str, Any] | None = None,
        status: StepStatus = StepStatus.PENDING,
    ) -> DurableStep:
        """Helper to create and persist a durable step."""
        step = DurableStep(
            step_id=str(uuid.uuid4()),
            run_id=run_id,
            step_index=step_index,
            action_type=action_type,
            tool_name=tool_name,
            idempotency_key=idempotency_key,
            status=status,
            args=args or {},
            is_side_effect=is_side_effect,
        )
        self.save_step(step)
        return step

    def mark_step_in_flight(self, step_id: str) -> None:
        """Mark a step as in flight."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE durable_steps SET status = ?, updated_at = ? WHERE step_id = ?",
                (StepStatus.IN_FLIGHT.value, datetime.now(UTC).isoformat(), step_id),
            )

    def update_run_status(self, run_id: str, status: RunStatus) -> None:
        """Update run status directly."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE durable_runs SET status = ?, updated_at = ? WHERE run_id = ?",
                (status.value, datetime.now(UTC).isoformat(), run_id),
            )

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS durable_runs (
                    run_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    workflow_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    initial_input TEXT NOT NULL,
                    current_step_index INTEGER NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_durable_runs_tenant
                ON durable_runs(tenant_id, status);

                CREATE TABLE IF NOT EXISTS durable_steps (
                    step_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    step_index INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    tool_name TEXT,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    args TEXT NOT NULL,
                    result TEXT,
                    error TEXT,
                    approval_ticket_id TEXT,
                    is_side_effect INTEGER NOT NULL,
                    compensation_action TEXT,
                    compensation_args TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES durable_runs(run_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_durable_steps_run
                ON durable_steps(run_id, step_index);
                """
            )

    def save_run(self, run: DurableRun) -> None:
        """Upsert a durable run."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO durable_runs (
                    run_id, tenant_id, workflow_name, status, initial_input,
                    current_step_index, metadata, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status = excluded.status,
                    current_step_index = excluded.current_step_index,
                    metadata = excluded.metadata,
                    updated_at = excluded.updated_at
                """,
                (
                    run.run_id,
                    run.tenant_id,
                    run.workflow_name,
                    run.status.value,
                    json.dumps(run.initial_input),
                    run.current_step_index,
                    json.dumps(run.metadata),
                    run.created_at.isoformat(),
                    datetime.now(UTC).isoformat(),
                ),
            )

    def get_run(self, run_id: str, tenant_id: str | None = None) -> DurableRun | None:
        """Retrieve a run with all associated steps."""
        active_tenant = tenant_id or TenantContext.get_current()
        with self._get_connection() as conn:
            query = "SELECT * FROM durable_runs WHERE run_id = ?"
            params: list[Any] = [run_id]
            if active_tenant:
                query += " AND tenant_id = ?"
                params.append(active_tenant)

            row = conn.execute(query, params).fetchone()
            if not row:
                return None

            steps_cursor = conn.execute(
                "SELECT * FROM durable_steps WHERE run_id = ? ORDER BY step_index ASC",
                (run_id,),
            )
            steps = []
            for s in steps_cursor.fetchall():
                steps.append(
                    DurableStep(
                        step_id=s["step_id"],
                        run_id=s["run_id"],
                        step_index=s["step_index"],
                        action_type=s["action_type"],
                        tool_name=s["tool_name"],
                        idempotency_key=s["idempotency_key"],
                        status=StepStatus(s["status"]),
                        args=json.loads(s["args"]),
                        result=json.loads(s["result"]) if s["result"] else None,
                        error=s["error"],
                        approval_ticket_id=s["approval_ticket_id"],
                        is_side_effect=bool(s["is_side_effect"]),
                        compensation_action=s["compensation_action"],
                        compensation_args=(
                            json.loads(s["compensation_args"])
                            if s["compensation_args"]
                            else None
                        ),
                        created_at=datetime.fromisoformat(s["created_at"]),
                        updated_at=datetime.fromisoformat(s["updated_at"]),
                    )
                )

            return DurableRun(
                run_id=row["run_id"],
                tenant_id=row["tenant_id"],
                workflow_name=row["workflow_name"],
                status=RunStatus(row["status"]),
                initial_input=json.loads(row["initial_input"]),
                current_step_index=row["current_step_index"],
                steps=steps,
                metadata=json.loads(row["metadata"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )

    def save_step(self, step: DurableStep) -> None:
        """Upsert an execution step."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO durable_steps (
                    step_id, run_id, step_index, action_type, tool_name,
                    idempotency_key, status, args, result, error,
                    approval_ticket_id, is_side_effect, compensation_action,
                    compensation_args, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(step_id) DO UPDATE SET
                    status = excluded.status,
                    result = excluded.result,
                    error = excluded.error,
                    approval_ticket_id = excluded.approval_ticket_id,
                    updated_at = excluded.updated_at
                """,
                (
                    step.step_id,
                    step.run_id,
                    step.step_index,
                    step.action_type,
                    step.tool_name,
                    step.idempotency_key,
                    step.status.value,
                    json.dumps(step.args),
                    json.dumps(step.result) if step.result is not None else None,
                    step.error,
                    step.approval_ticket_id,
                    1 if step.is_side_effect else 0,
                    step.compensation_action,
                    json.dumps(step.compensation_args)
                    if step.compensation_args
                    else None,
                    step.created_at.isoformat(),
                    datetime.now(UTC).isoformat(),
                ),
            )

    def get_step_by_idempotency_key(self, idempotency_key: str) -> DurableStep | None:
        """Check for existing step execution via deterministic idempotency key."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM durable_steps WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if not row:
                return None
            return DurableStep(
                step_id=row["step_id"],
                run_id=row["run_id"],
                step_index=row["step_index"],
                action_type=row["action_type"],
                tool_name=row["tool_name"],
                idempotency_key=row["idempotency_key"],
                status=StepStatus(row["status"]),
                args=json.loads(row["args"]),
                result=json.loads(row["result"]) if row["result"] else None,
                error=row["error"],
                approval_ticket_id=row["approval_ticket_id"],
                is_side_effect=bool(row["is_side_effect"]),
                compensation_action=row["compensation_action"],
                compensation_args=(
                    json.loads(row["compensation_args"])
                    if row["compensation_args"]
                    else None
                ),
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )


class DurableExecutionCoordinator:
    """Orchestrates crash-resilient execution, idempotency, approvals, and compensation."""

    def __init__(self, store: DurableRunStore) -> None:
        self.store = store

    @staticmethod
    def compute_idempotency_key(
        run_id: str,
        step_index: int,
        action_type: str,
        args: dict[str, Any],
    ) -> str:
        """Derive deterministic idempotency digest for a step."""
        raw = f"{run_id}:{step_index}:{action_type}:{json.dumps(args, sort_keys=True)}"
        digest = hashlib.sha256(raw.encode()).hexdigest()[:24]
        return f"idemp_{digest}"

    def start_run(
        self,
        workflow_name: str,
        initial_input: dict[str, Any],
        run_id: str | None = None,
        tenant_id: str | None = None,
    ) -> DurableRun:
        """Initialize a new durable run."""
        rid = run_id or f"run_{uuid.uuid4().hex[:12]}"
        tid = tenant_id or TenantContext.get_current() or "default"

        run = DurableRun(
            run_id=rid,
            tenant_id=tid,
            workflow_name=workflow_name,
            status=RunStatus.RUNNING,
            initial_input=initial_input,
            current_step_index=0,
        )
        self.store.save_run(run)
        logger.info("Initialized durable run {} [{}] for tenant {}", rid, workflow_name, tid)
        return run

    async def execute_step(
        self,
        run_id: str,
        step_index: int,
        action_type: str,
        action_func: Callable[[], Awaitable[Any]],
        args: dict[str, Any],
        tool_name: str | None = None,
        is_side_effect: bool = False,
        compensation: tuple[str, dict[str, Any]] | None = None,
    ) -> Any:
        """Execute a workflow step with idempotency protection and crash tracking."""
        idemp_key = self.compute_idempotency_key(run_id, step_index, action_type, args)

        # 1. Deduplication check: return cached outcome if step already completed
        existing = self.store.get_step_by_idempotency_key(idemp_key)
        if existing and existing.status == StepStatus.COMPLETED:
            logger.info(
                "Idempotency cache hit: Step {} of run {} previously completed. Skipping duplicate action.",
                step_index,
                run_id,
            )
            return existing.result

        step_id = existing.step_id if existing else f"step_{uuid.uuid4().hex[:12]}"
        comp_action, comp_args = compensation if compensation else (None, None)

        step = DurableStep(
            step_id=step_id,
            run_id=run_id,
            step_index=step_index,
            action_type=action_type,
            tool_name=tool_name,
            idempotency_key=idemp_key,
            status=StepStatus.IN_FLIGHT,
            args=args,
            is_side_effect=is_side_effect,
            compensation_action=comp_action,
            compensation_args=comp_args,
        )
        self.store.save_step(step)

        # Update run pointer
        run = self.store.get_run(run_id)
        if run:
            run.current_step_index = step_index
            run.status = RunStatus.RUNNING
            self.store.save_run(run)

        # 2. Execute target action
        try:
            result = await action_func()
            step.status = StepStatus.COMPLETED
            step.result = result
            self.store.save_step(step)
            return result
        except Exception as exc:
            # If a side-effect step fails ambiguously (e.g. transport drop during side effect)
            step.status = StepStatus.AMBIGUOUS if is_side_effect else StepStatus.FAILED
            step.error = str(exc)
            self.store.save_step(step)
            if run:
                run.status = (
                    RunStatus.AMBIGUOUS if is_side_effect else RunStatus.FAILED
                )
                self.store.save_run(run)
            raise

    def record_pending_approval(
        self,
        run_id: str,
        step_index: int,
        ticket_id: str,
        action_name: str,
        args: dict[str, Any],
    ) -> DurableStep:
        """Record an action paused for human approval."""
        idemp_key = self.compute_idempotency_key(run_id, step_index, "approval", args)
        step = DurableStep(
            step_id=f"step_{uuid.uuid4().hex[:12]}",
            run_id=run_id,
            step_index=step_index,
            action_type="approval_request",
            tool_name=action_name,
            idempotency_key=idemp_key,
            status=StepStatus.IN_FLIGHT,
            approval_ticket_id=ticket_id,
            args=args,
            is_side_effect=True,
        )
        self.store.save_step(step)

        run = self.store.get_run(run_id)
        if run:
            run.status = RunStatus.WAITING_FOR_APPROVAL
            run.current_step_index = step_index
            self.store.save_run(run)

        logger.info(
            "Run {} paused at step {} waiting for approval ticket {}",
            run_id,
            step_index,
            ticket_id,
        )
        return step

    def analyze_recovery(self, run_id: str) -> RecoveryReport:
        """Inspect a potentially interrupted run and generate a recovery diagnostics report."""
        run = self.store.get_run(run_id)
        if not run:
            raise KeyError(f"Run '{run_id}' not found")

        completed_count = 0
        in_flight_count = 0
        ambiguous_steps: list[str] = []
        pending_ticket: str | None = None
        next_step_index = 0

        for step in run.steps:
            if step.status == StepStatus.COMPLETED:
                completed_count += 1
                next_step_index = max(next_step_index, step.step_index + 1)
            elif step.status == StepStatus.IN_FLIGHT:
                in_flight_count += 1
                if step.approval_ticket_id:
                    pending_ticket = step.approval_ticket_id
                elif step.is_side_effect:
                    ambiguous_steps.append(step.step_id)
                next_step_index = max(next_step_index, step.step_index)
            elif step.status == StepStatus.AMBIGUOUS:
                ambiguous_steps.append(step.step_id)
                next_step_index = max(next_step_index, step.step_index)

        can_auto_resume = len(ambiguous_steps) == 0 and pending_ticket is None

        if ambiguous_steps:
            summary = (
                f"Run crashed during side-effect execution. Ambiguous steps detected: {ambiguous_steps}. "
                "Manual or operator reconciliation required before side-effect retry."
            )
            rec_status = RunStatus.AMBIGUOUS
        elif pending_ticket:
            summary = (
                f"Run survived process crash. Pending human approval ticket '{pending_ticket}' "
                "is intact and awaiting resolution."
            )
            rec_status = RunStatus.WAITING_FOR_APPROVAL
        elif run.status == RunStatus.COMPLETED:
            summary = "Run previously finished all steps successfully."
            rec_status = RunStatus.COMPLETED
        else:
            summary = f"Run can safely resume from step index {next_step_index} without duplicate actions."
            rec_status = RunStatus.RUNNING

        return RecoveryReport(
            run_id=run.run_id,
            tenant_id=run.tenant_id,
            recovered_status=rec_status,
            total_steps=len(run.steps),
            completed_steps=completed_count,
            in_flight_steps_found=in_flight_count,
            ambiguous_steps=ambiguous_steps,
            pending_approval_ticket=pending_ticket,
            resume_step_index=next_step_index,
            can_auto_resume=can_auto_resume,
            summary=summary,
        )

    def recover_run(self, run_id: str) -> RecoveryReport | None:
        """Inspect and reconcile an interrupted run, updating its persistent state."""
        try:
            report = self.analyze_recovery(run_id)
        except KeyError:
            return None
        self.store.update_run_status(run_id, report.recovered_status)
        return report

    async def compensate_run(
        self,
        run_id: str,
        executor_map: dict[str, Callable[[dict[str, Any]], Awaitable[None]]],
    ) -> list[str]:
        """Execute registered compensating actions in reverse order to roll back side effects."""
        run = self.store.get_run(run_id)
        if not run:
            raise KeyError(f"Run '{run_id}' not found")

        run.status = RunStatus.COMPENSATING
        self.store.save_run(run)

        compensated_steps: list[str] = []

        # Iterate completed steps in reverse
        for step in reversed(run.steps):
            if step.status == StepStatus.COMPLETED and step.compensation_action:
                action_name = step.compensation_action
                handler = executor_map.get(action_name)
                if handler:
                    args = step.compensation_args or {}
                    logger.info(
                        "Compensating step {} using action {} with args {}",
                        step.step_id,
                        action_name,
                        args,
                    )
                    await handler(args)
                    step.status = StepStatus.COMPENSATED
                    self.store.save_step(step)
                    compensated_steps.append(step.step_id)

        run.status = RunStatus.COMPENSATED
        self.store.save_run(run)
        logger.info("Run {} compensation completed. Steps reverted: {}", run_id, compensated_steps)
        return compensated_steps
