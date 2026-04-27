"""Cost and usage tracking for LLM calls."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from amberclaw.providers.base import LLMResponse

_COST_LOG_PATH = Path.home() / ".amberclaw" / "usage.jsonl"


def log_usage(model: str, response: LLMResponse) -> None:
    """Log LLM usage and cost to a local file."""
    try:
        _COST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "model": model,
            "input_tokens": response.usage.get("prompt_tokens", 0),
            "output_tokens": response.usage.get("completion_tokens", 0),
            "total_tokens": response.usage.get("total_tokens", 0),
            "cost": response.cost,
            "latency_ms": response.latency_ms,
            "ttft_ms": response.ttft_ms,
        }

        with open(_COST_LOG_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        # Silently fail for logging errors
        pass


def get_total_costs() -> dict[str, Any]:
    """Calculate total costs from logs."""
    if not _COST_LOG_PATH.exists():
        return {"total_cost": 0.0, "total_tokens": 0, "sessions": 0}

    total_cost = 0.0
    total_tokens = 0
    calls = 0

    try:
        with open(_COST_LOG_PATH, "r") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    total_cost += data.get("cost", 0.0)
                    total_tokens += data.get("total_tokens", 0)
                    calls += 1
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass

    return {
        "total_cost": total_cost,
        "total_tokens": total_tokens,
        "total_calls": calls,
    }
