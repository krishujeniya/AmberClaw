"""Usage grouping respects the selected reporting window and actual log rows."""

import json
from datetime import UTC, datetime, timedelta

from amberclaw.utils import cost_tracker


def test_model_costs_group_real_rows_and_filter_old_usage(monkeypatch, tmp_path):
    now = datetime.now(UTC)
    rows = [
        {
            "timestamp": now.isoformat(),
            "model": "a",
            "cost": 0.25,
            "total_tokens": 10,
            "latency_ms": 20,
        },
        {
            "timestamp": now.isoformat(),
            "model": "a",
            "cost": 0.75,
            "total_tokens": 30,
            "latency_ms": 40,
        },
        {
            "timestamp": (now - timedelta(days=30)).isoformat(),
            "model": "b",
            "cost": 2.0,
            "total_tokens": 100,
        },
    ]
    log = tmp_path / "usage.jsonl"
    log.write_text("\n".join(json.dumps(row) for row in rows) + "\ninvalid\n[]\n")
    monkeypatch.setattr(cost_tracker, "_COST_LOG_PATH", log)
    expected_tokens = 40
    expected_calls = 2
    expected_latency = 30.0
    recent = cost_tracker.get_model_costs(days=7)
    assert set(recent) == {"a"}
    assert recent["a"]["total_cost"] == 1.0
    assert recent["a"]["total_tokens"] == expected_tokens
    assert recent["a"]["calls"] == expected_calls
    assert recent["a"]["avg_latency_ms"] == expected_latency
    assert set(cost_tracker.get_model_costs(days=None)) == {"a", "b"}


def test_model_costs_return_empty_for_missing_log(monkeypatch, tmp_path):
    monkeypatch.setattr(cost_tracker, "_COST_LOG_PATH", tmp_path / "missing.jsonl")
    assert cost_tracker.get_model_costs(days=None) == {}
