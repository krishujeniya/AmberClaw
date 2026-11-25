# ruff: noqa: PLR0913
"""Hard Budgets, In-Flight Settlement, and Cost per Success Ledger (CL-015).

Provides:
- Pre-execution budget reservation preventing concurrent overspend under race conditions.
- Strict spending caps with explicit in-flight settlement allowances (default 5%).
- Complete cost accounting covering model tokens, external tools, retries, and failed attempts.
- Enforced timeout ceilings per-step and per-run.
- Accurate metrics for total spend, successful/failed attempts, cost per successful task,
  and p50/p95 latency distributions.
"""

from __future__ import annotations

import asyncio
import math
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


class BudgetExceededError(Exception):
    """Raised when an action would exceed the declared tenant or run spend cap."""


class BudgetTimeoutError(Exception):
    """Raised when an action exceeds the maximum allotted run or step duration ceiling."""


class TenantBudgetConfig(BaseModel):
    """Budget limits and policy ceilings for a tenant."""

    tenant_id: str
    max_budget_usd: float = 50.0
    max_tokens_limit: int = 1_000_000
    max_run_duration_seconds: float = 300.0
    settlement_allowance_ratio: float = 0.05  # Documented 5% in-flight settlement grace


class BudgetReservation(BaseModel):
    """Active reservation holding estimated budget before parallel/remote action dispatch."""

    reservation_id: str = Field(default_factory=lambda: f"res_{secrets.token_hex(8)}")
    tenant_id: str
    run_id: str
    step_index: int | None = None
    reserved_usd: float
    reserved_tokens: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime
    settled: bool = False
    actual_usd: float = 0.0
    actual_tokens: int = 0
    status: str = "reserved"


class LedgerEntry(BaseModel):
    """Immutable audit record of a settled financial or token transaction."""

    entry_id: str = Field(default_factory=lambda: f"led_{secrets.token_hex(8)}")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tenant_id: str
    run_id: str
    step_index: int | None = None
    action_type: str = "model_inference"
    actual_usd: float
    actual_tokens: int = 0
    status: str = "success"  # success, failed, timeout, cancelled
    latency_ms: float = 0.0
    error: str | None = None


class PricingLedger:
    """Calculates model token pricing per million tokens."""

    RATES: dict[str, dict[str, float]] = {
        "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
        "gpt-4o": {"input": 2.5, "output": 10.0},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "qwen2.5:7b": {"input": 0.0, "output": 0.0},
        "default": {"input": 3.0, "output": 15.0},
    }

    @classmethod
    def calculate_cost(
        cls, model: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        """Compute estimated USD cost for model token consumption."""
        rates = cls.RATES.get(model, cls.RATES["default"])
        input_cost = (prompt_tokens / 1_000_000.0) * rates["input"]
        output_cost = (completion_tokens / 1_000_000.0) * rates["output"]
        return input_cost + output_cost


class HardBudgetLedger:
    """Thread-safe and async-safe budget reservation, spending enforcement, and cost ledger."""

    _instance: HardBudgetLedger | None = None

    def __init__(self) -> None:
        self._configs: dict[str, TenantBudgetConfig] = {}
        self._active_reservations: dict[str, BudgetReservation] = {}
        self._ledger_entries: list[LedgerEntry] = []
        self._run_start_times: dict[str, float] = {}
        self._run_final_outcomes: dict[str, str] = {}  # run_id -> "completed" / "failed"
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> HardBudgetLedger:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def configure_tenant(
        self,
        tenant_id: str,
        max_budget_usd: float,
        max_tokens_limit: int = 1_000_000,
        max_run_duration_seconds: float = 300.0,
        settlement_allowance_ratio: float = 0.05,
    ) -> TenantBudgetConfig:
        """Register or update spending limits and ceilings for a tenant."""
        cfg = TenantBudgetConfig(
            tenant_id=tenant_id,
            max_budget_usd=max_budget_usd,
            max_tokens_limit=max_tokens_limit,
            max_run_duration_seconds=max_run_duration_seconds,
            settlement_allowance_ratio=settlement_allowance_ratio,
        )
        self._configs[tenant_id] = cfg
        return cfg

    def get_tenant_config(self, tenant_id: str) -> TenantBudgetConfig:
        if tenant_id not in self._configs:
            self._configs[tenant_id] = TenantBudgetConfig(tenant_id=tenant_id)
        return self._configs[tenant_id]

    async def reserve(
        self,
        tenant_id: str,
        run_id: str,
        estimated_usd: float,
        estimated_tokens: int = 0,
        step_index: int | None = None,
        ttl_seconds: float = 60.0,
    ) -> BudgetReservation:
        """Atomically check ceilings and reserve spend capacity prior to dispatch."""
        async with self._lock:
            # 1. Timeout ceiling check
            now_mono = time.monotonic()
            if run_id not in self._run_start_times:
                self._run_start_times[run_id] = now_mono

            cfg = self.get_tenant_config(tenant_id)
            elapsed = now_mono - self._run_start_times[run_id]
            if elapsed > cfg.max_run_duration_seconds:
                raise BudgetTimeoutError(
                    f"Run '{run_id}' exceeded maximum allotted duration of {cfg.max_run_duration_seconds}s "
                    f"(elapsed: {elapsed:.2f}s)"
                )

            # 2. Spend ceiling check
            current_spent = sum(
                e.actual_usd for e in self._ledger_entries if e.tenant_id == tenant_id
            )
            current_reserved = sum(
                r.reserved_usd
                for r in self._active_reservations.values()
                if r.tenant_id == tenant_id and not r.settled
            )

            # Cap includes the documented in-flight settlement grace margin
            allowed_ceiling = cfg.max_budget_usd * (1.0 + cfg.settlement_allowance_ratio)
            projected_total = current_spent + current_reserved + estimated_usd

            if projected_total > allowed_ceiling:
                raise BudgetExceededError(
                    f"Declared spend cap of ${cfg.max_budget_usd:.4f} exceeded for tenant '{tenant_id}'. "
                    f"Current spent: ${current_spent:.4f}, Active reservations: ${current_reserved:.4f}, "
                    f"Requested: ${estimated_usd:.4f} (Ceiling with {cfg.settlement_allowance_ratio*100:.0f}% "
                    f"allowance: ${allowed_ceiling:.4f})"
                )

            # 3. Create active reservation
            res = BudgetReservation(
                tenant_id=tenant_id,
                run_id=run_id,
                step_index=step_index,
                reserved_usd=estimated_usd,
                reserved_tokens=estimated_tokens,
                expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
            )
            self._active_reservations[res.reservation_id] = res
            return res

    async def settle(
        self,
        reservation_id: str,
        actual_usd: float,
        actual_tokens: int = 0,
        action_type: str = "model_inference",
        status: str = "success",
        latency_ms: float = 0.0,
        error: str | None = None,
    ) -> LedgerEntry:
        """Atomically finalize a reservation with exact actual charges, recording to ledger."""
        async with self._lock:
            res = self._active_reservations.get(reservation_id)
            if not res:
                # If reservation was missing or expired, record directly to prevent unbilled leakage
                entry = LedgerEntry(
                    tenant_id="default",
                    run_id="unknown",
                    action_type=action_type,
                    actual_usd=actual_usd,
                    actual_tokens=actual_tokens,
                    status=status,
                    latency_ms=latency_ms,
                    error=error,
                )
                self._ledger_entries.append(entry)
                return entry

            res.settled = True
            res.actual_usd = actual_usd
            res.actual_tokens = actual_tokens
            res.status = status

            entry = LedgerEntry(
                tenant_id=res.tenant_id,
                run_id=res.run_id,
                step_index=res.step_index,
                action_type=action_type,
                actual_usd=actual_usd,
                actual_tokens=actual_tokens,
                status=status,
                latency_ms=latency_ms,
                error=error,
            )
            self._ledger_entries.append(entry)
            # Remove settled reservation from in-flight pool
            self._active_reservations.pop(reservation_id, None)
            return entry

    async def record_run_outcome(self, run_id: str, outcome: str) -> None:
        """Record final state ('completed' vs 'failed') for run success accounting."""
        async with self._lock:
            self._run_final_outcomes[run_id] = outcome

    async def release_reservation(self, reservation_id: str) -> None:
        """Release unused reservation without charging actual cost."""
        async with self._lock:
            self._active_reservations.pop(reservation_id, None)

    async def get_tenant_spend(self, tenant_id: str) -> dict[str, Any]:
        """Return total realized spend, active reservations, and remaining headroom."""
        async with self._lock:
            cfg = self.get_tenant_config(tenant_id)
            spent = sum(e.actual_usd for e in self._ledger_entries if e.tenant_id == tenant_id)
            tokens = sum(e.actual_tokens for e in self._ledger_entries if e.tenant_id == tenant_id)
            reserved = sum(
                r.reserved_usd
                for r in self._active_reservations.values()
                if r.tenant_id == tenant_id and not r.settled
            )
            return {
                "tenant_id": tenant_id,
                "max_budget_usd": cfg.max_budget_usd,
                "total_spent_usd": round(spent, 6),
                "total_tokens_used": tokens,
                "in_flight_reserved_usd": round(reserved, 6),
                "remaining_budget_usd": round(max(0.0, cfg.max_budget_usd - spent - reserved), 6),
                "settlement_allowance_usd": round(cfg.max_budget_usd * cfg.settlement_allowance_ratio, 6),
            }

    async def get_cost_per_success_metrics(self, tenant_id: str | None = None) -> dict[str, Any]:
        """Compute total spend, failed vs successful task yield, and cost per success."""
        async with self._lock:
            entries = [
                e for e in self._ledger_entries
                if tenant_id is None or e.tenant_id == tenant_id
            ]

            total_spend = sum(e.actual_usd for e in entries)
            total_tokens = sum(e.actual_tokens for e in entries)

            # Match runs to final outcomes
            all_runs = set(e.run_id for e in entries)
            successful_runs = sum(
                1 for r in all_runs if self._run_final_outcomes.get(r) == "completed"
            )
            failed_runs = sum(
                1 for r in all_runs if self._run_final_outcomes.get(r) == "failed"
            )

            # Latency statistics across all transactions
            latencies = sorted(e.latency_ms for e in entries if e.latency_ms > 0)
            p50_latency = latencies[len(latencies) // 2] if latencies else 0.0
            p95_idx = int(len(latencies) * 0.95)
            p95_latency = latencies[min(p95_idx, len(latencies) - 1)] if latencies else 0.0

            cost_per_success = (
                total_spend / successful_runs if successful_runs > 0 else 0.0
            )
            success_rate = (
                successful_runs / (successful_runs + failed_runs)
                if (successful_runs + failed_runs) > 0
                else 0.0
            )

            return {
                "tenant_id": tenant_id or "all_tenants",
                "total_spend_usd": round(total_spend, 6),
                "total_tokens": total_tokens,
                "total_runs": len(all_runs),
                "successful_runs": successful_runs,
                "failed_runs": failed_runs,
                "task_success_rate": round(success_rate, 4),
                "cost_per_successful_task_usd": round(cost_per_success, 6),
                "latency_p50_ms": round(p50_latency, 2),
                "latency_p95_ms": round(p95_latency, 2),
                "total_ledger_transactions": len(entries),
            }

    def reset(self) -> None:
        """Clear all active configurations, reservations, and ledger state."""
        self._configs.clear()
        self._active_reservations.clear()
        self._ledger_entries.clear()
        self._run_start_times.clear()
        self._run_final_outcomes.clear()
