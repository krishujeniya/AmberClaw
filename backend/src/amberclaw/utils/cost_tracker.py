"""Cost and usage tracking for LLM calls."""

import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TypedDict

from loguru import logger

from amberclaw.providers.base import LLMResponse

_COST_LOG_PATH = Path.home() / ".amberclaw" / "usage.jsonl"


def log_usage(model: str, response: LLMResponse) -> None:
    """Log LLM usage and cost to a local file."""
    try:
        _COST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "model": model,
            "input_tokens": response.usage.get("prompt_tokens", 0),
            "output_tokens": response.usage.get("completion_tokens", 0),
            "total_tokens": response.usage.get("total_tokens", 0),
            "cost": response.cost,
            "latency_ms": response.latency_ms,
            "ttft_ms": response.ttft_ms,
        }

        with Path(_COST_LOG_PATH).open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        # Silently fail for logging errors
        logger.debug(
            "Optional operation failed in cost_tracker; using the existing fallback"
        )


class ModelUsage(TypedDict):
    calls: int
    total_tokens: int
    total_cost: float
    avg_latency_ms: float


def _finite_number(value: object) -> float:
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    ):
        return float(value)
    return 0.0


def _within_window(data: dict[str, Any], cutoff: datetime | None) -> bool:
    if cutoff is None:
        return True
    timestamp = data.get("timestamp")
    if not isinstance(timestamp, str):
        return False
    try:
        recorded = datetime.fromisoformat(timestamp)
    except ValueError:
        return False
    if recorded.tzinfo is None:
        recorded = recorded.replace(tzinfo=UTC)
    return recorded >= cutoff


def get_model_costs(days: int | None = None) -> dict[str, ModelUsage]:
    """Group actual usage rows by model within the requested UTC reporting window."""
    if days is not None and days < 1:
        raise ValueError("days must be positive")
    cutoff = datetime.now(UTC) - timedelta(days=days) if days is not None else None
    models: dict[str, ModelUsage] = {}
    latency_totals: dict[str, float] = {}
    try:
        with _COST_LOG_PATH.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    data = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(data, dict) or not _within_window(data, cutoff):
                    continue
                model = data.get("model")
                if not isinstance(model, str) or not model:
                    model = "unknown"
                stats = models.setdefault(
                    model,
                    {
                        "calls": 0,
                        "total_tokens": 0,
                        "total_cost": 0.0,
                        "avg_latency_ms": 0.0,
                    },
                )
                stats["calls"] += 1
                stats["total_tokens"] += int(_finite_number(data.get("total_tokens")))
                stats["total_cost"] += _finite_number(data.get("cost"))
                latency_totals[model] = latency_totals.get(model, 0.0) + _finite_number(
                    data.get("latency_ms")
                )
    except FileNotFoundError:
        return {}
    except OSError:
        logger.debug("Usage log could not be read; returning rows read so far")
    for model, stats in models.items():
        stats["avg_latency_ms"] = latency_totals[model] / stats["calls"]
    return models


def get_total_costs() -> dict[str, Any]:
    """Calculate all-time totals from the same validated rows as model reporting."""
    models = get_model_costs()
    return {
        "total_cost": sum(stats["total_cost"] for stats in models.values()),
        "total_tokens": sum(stats["total_tokens"] for stats in models.values()),
        "total_calls": sum(stats["calls"] for stats in models.values()),
    }
