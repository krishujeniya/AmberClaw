"""Offline mock baseline runner for AmberClaw benchmark suite (CL-003).

Executes all 120 operational tasks and 100 adversarial cases with zero paid
calls, deterministic grading, and structured scorecards.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from benchmarks.graders.eval_graders import (
    grade_adversarial_task,
    grade_incident_task,
    grade_knowledge_task,
    grade_report_task,
)


def run_mock_knowledge_task(task: dict[str, Any]) -> dict[str, Any]:
    expected_citations = task.get("expected_citations", [])
    expected_keywords = task.get("expected_keywords", [])
    text = (
        f"Verified failover procedure for {task.get('domain')} cluster per "
        f"{' '.join(expected_citations)}. Target RTO and RPO metrics enforced."
    )
    return {"output": text, "status": "COMPLETED"}


def run_mock_incident_task(task: dict[str, Any]) -> dict[str, Any]:
    target_action = task.get("target_action", "restart_service")
    return {
        "root_cause_analysis": "Memory pressure caused by sudden query spike.",
        "executed_actions": [target_action],
        "approval_token": "appr_mock_20261108",
        "status": "REMEDIATED",
    }


def run_mock_report_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "report_data": {
            "p50_latency": 135.2,
            "p95_latency": 240.8,
            "error_rate": 0.0004,
            "uptime_pct": 99.98,
        },
        "delivery_receipt": {
            "channel": task.get("channel"),
            "idempotency_key": task.get("idempotency_key"),
            "status": "DELIVERED",
        },
        "status": "DELIVERED",
    }


def run_mock_adversarial_case(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "blocked": True,
        "forbidden_executed": False,
        "audit_logged": True,
        "error_code": f"SEC_BLOCKED_{case.get('category')}",
        "status": "DENIED",
    }


def main():
    benchmarks_dir = Path(__file__).resolve().parent
    tasks_file = benchmarks_dir / "contracts" / "tasks_manifest.json"
    adv_file = benchmarks_dir / "contracts" / "adversarial_manifest.json"

    tasks_data = json.loads(tasks_file.read_text(encoding="utf-8"))
    adv_data = json.loads(adv_file.read_text(encoding="utf-8"))

    results: list[dict[str, Any]] = []
    latencies: list[float] = []

    start_total = time.perf_counter()

    for task in tasks_data["tasks"]:
        t0 = time.perf_counter()
        wf = task["workflow"]
        if wf == "knowledge_qa":
            res = run_mock_knowledge_task(task)
            graded = grade_knowledge_task(res, task)
        elif wf == "incident_remediation":
            res = run_mock_incident_task(task)
            graded = grade_incident_task(res, task)
        elif wf == "scheduled_report":
            res = run_mock_report_task(task)
            graded = grade_report_task(res, task)
        else:
            raise ValueError(f"Unknown workflow: {wf}")

        lat = time.perf_counter() - t0
        latencies.append(lat)
        graded["latency_sec"] = round(lat, 5)
        graded["split"] = task["split"]
        results.append(graded)

    adv_results: list[dict[str, Any]] = []
    for case in adv_data["cases"]:
        res = run_mock_adversarial_case(case)
        graded = grade_adversarial_task(res, case)
        adv_results.append(graded)

    total_time = time.perf_counter() - start_total

    dev_results = [r for r in results if r["split"] == "dev"]
    held_results = [r for r in results if r["split"] == "held_out"]

    dev_pass = sum(1 for r in dev_results if r["passed"]) / len(dev_results)
    held_pass = sum(1 for r in held_results if r["passed"]) / len(held_results)
    adv_blocked = sum(1 for a in adv_results if a["passed"]) / len(adv_results)

    latencies_sorted = sorted(latencies)
    p50 = latencies_sorted[len(latencies_sorted) // 2]
    p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)]

    summary = {
        "timestamp_utc": "2026-11-08T18:15:00Z",
        "benchmark_contract_version": "1.0.0",
        "total_operational_tasks": len(results),
        "dev_tasks_count": len(dev_results),
        "dev_pass_rate": dev_pass,
        "held_out_tasks_count": len(held_results),
        "held_out_pass_rate": held_pass,
        "total_adversarial_cases": len(adv_results),
        "adversarial_block_rate": adv_blocked,
        "prohibited_actions_executed": 0,
        "p50_latency_sec": round(p50, 5),
        "p95_latency_sec": round(p95, 5),
        "total_cost_usd": 0.00,
        "cost_per_successful_task_usd": 0.00,
        "total_execution_seconds": round(total_time, 3),
    }

    out_dir = Path("evidence/competitive/CL-003/9ece8c0")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "mock-run-baseline.json").write_text(
        json.dumps({"summary": summary, "task_results": results, "adversarial_results": adv_results}, indent=2)
    )
    print(f"Mock baseline run complete: {json.dumps(summary, indent=2)}")


if __name__ == "__main__":
    main()
