# ruff: noqa: DTZ003
"""SLO Alert Engine and Audit Log Health Continuity Monitor."""

from __future__ import annotations

import hashlib
import json
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class AlertNotification:
    alert_id: str
    rule_name: str
    severity: str  # "warning", "critical"
    message: str
    triggered_at: str
    current_value: float
    threshold: float
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SLOMonitor:
    """Monitors Service Level Objectives (SLOs) and calculates error budget burn rates."""

    def __init__(
        self,
        window_size: int = 500,
        availability_target: float = 0.99,  # 99.0% availability
        p95_latency_target_ms: float = 1000.0,
    ):
        self.window_size = window_size
        self.availability_target = availability_target
        self.p95_latency_target_ms = p95_latency_target_ms

        self._requests: deque[bool] = deque(
            maxlen=window_size
        )  # True = success, False = failure
        self._latencies_ms: deque[float] = deque(maxlen=window_size)
        self._alerts: list[AlertNotification] = []

    def record_request(self, success: bool, latency_ms: float) -> None:
        """Record an operation outcome and its execution latency."""
        self._requests.append(success)
        self._latencies_ms.append(latency_ms)

    @property
    def total_recorded(self) -> int:
        return len(self._requests)

    @property
    def current_availability(self) -> float:
        if not self._requests:
            return 1.0
        return sum(1 for r in self._requests if r) / len(self._requests)

    @property
    def p95_latency_ms(self) -> float:
        if not self._latencies_ms:
            return 0.0
        sorted_lat = sorted(self._latencies_ms)
        idx = int(0.95 * len(sorted_lat))
        return sorted_lat[min(idx, len(sorted_lat) - 1)]

    @property
    def error_budget_remaining(self) -> float:
        """Percentage of error budget remaining in the current window."""
        allowed_error_ratio = 1.0 - self.availability_target
        if allowed_error_ratio <= 0:
            return 0.0
        actual_error_ratio = 1.0 - self.current_availability
        return max(0.0, 1.0 - (actual_error_ratio / allowed_error_ratio))

    def evaluate_rules(self) -> list[AlertNotification]:
        """Evaluate SLO thresholds and generate alerts if targets are breached."""
        new_alerts: list[AlertNotification] = []
        if len(self._requests) < 10:  # noqa: PLR2004
            return new_alerts

        now_iso = datetime.utcnow().isoformat()

        # 1. Availability SLO breach
        avail = self.current_availability
        if avail < self.availability_target:
            alert = AlertNotification(
                alert_id=f"alert_avail_{int(time.time())}",
                rule_name="AvailabilitySLOBreach",
                severity="critical"
                if avail < (self.availability_target - 0.05)
                else "warning",
                message=f"Current availability ({avail:.2%}) breached target ({self.availability_target:.2%})",
                triggered_at=now_iso,
                current_value=round(avail, 4),
                threshold=self.availability_target,
                details={
                    "window_size": len(self._requests),
                    "failed_requests": sum(1 for r in self._requests if not r),
                },
            )
            new_alerts.append(alert)

        # 2. Latency SLO breach
        p95 = self.p95_latency_ms
        if p95 > self.p95_latency_target_ms:
            alert = AlertNotification(
                alert_id=f"alert_lat_{int(time.time())}",
                rule_name="P95LatencySLOBreach",
                severity="warning",
                message=f"Current P95 latency ({p95:.1f}ms) exceeded threshold ({self.p95_latency_target_ms:.1f}ms)",
                triggered_at=now_iso,
                current_value=round(p95, 2),
                threshold=self.p95_latency_target_ms,
                details={"window_size": len(self._latencies_ms)},
            )
            new_alerts.append(alert)

        self._alerts.extend(new_alerts)
        return new_alerts


@dataclass
class AuditHealthReport:
    healthy: bool
    total_events: int
    verified_at: str
    broken_chain_index: int | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AuditLogHealthChecker:
    """Verifies SHA-256 cryptographic hash-chain continuity and tamper-evidence in audit logs."""

    @classmethod
    def verify_log_file(cls, log_path: Path | str) -> AuditHealthReport:
        path = Path(log_path)
        now_str = datetime.utcnow().isoformat()
        if not path.exists():
            return AuditHealthReport(
                healthy=False,
                total_events=0,
                verified_at=now_str,
                error=f"Audit log file not found: {path}",
            )

        events_count = 0
        expected_prev_hash = "GENESIS"

        try:
            with path.open("r", encoding="utf-8") as f:
                for line_idx, raw_line in enumerate(f):
                    line = raw_line.strip()
                    if not line:
                        continue
                    event_data = json.loads(line)
                    events_count += 1

                    # Check previous_hash chain link
                    prev_hash = event_data.get("previous_hash")
                    if prev_hash != expected_prev_hash:
                        return AuditHealthReport(
                            healthy=False,
                            total_events=events_count,
                            verified_at=now_str,
                            broken_chain_index=line_idx,
                            error=(
                                f"Hash chain broken at event #{line_idx}: expected "
                                f"previous_hash '{expected_prev_hash}', got '{prev_hash}'"
                            ),
                        )

                    # Verify entry hash integrity
                    current_hash = event_data.get("hash")
                    # Compute canonical hash excluding the hash field itself
                    entry_copy = {k: v for k, v in event_data.items() if k != "hash"}
                    canonical = json.dumps(entry_copy, sort_keys=True).encode("utf-8")
                    computed_hash = hashlib.sha256(canonical).hexdigest()

                    if current_hash != computed_hash:
                        return AuditHealthReport(
                            healthy=False,
                            total_events=events_count,
                            verified_at=now_str,
                            broken_chain_index=line_idx,
                            error=(
                                f"Tamper detected at event #{line_idx}: recorded hash '{current_hash}' "
                                f"does not match computed hash '{computed_hash}'"
                            ),
                        )

                    expected_prev_hash = current_hash

            return AuditHealthReport(
                healthy=True,
                total_events=events_count,
                verified_at=now_str,
            )
        except Exception as exc:
            logger.error("Audit log verification encountered error: {}", exc)
            return AuditHealthReport(
                healthy=False,
                total_events=events_count,
                verified_at=now_str,
                error=f"Parse error: {exc}",
            )
