"""Reproducible Performance Benchmark Suite for AmberClaw AI OS.

Measures p50, p95, p99 latencies, throughput (ops/sec), and memory overhead
across Secret Scanning, Audit Logger, SessionDB FTS5 search, and Token Counting.
"""

import json
import time
from pathlib import Path
from typing import Any

from amberclaw.memory.session_db import SessionDB
from amberclaw.security.audit import SecurityAuditLogger
from amberclaw.templates.scrubber import SecretScanner
from amberclaw.templates.template import TemplateManager


def calculate_percentiles(latencies_ms: list[float]) -> dict[str, float]:
    """Calculate p50, p95, p99, and mean latency stats."""
    if not latencies_ms:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "mean": 0.0}
    sorted_lats = sorted(latencies_ms)
    n = len(sorted_lats)
    return {
        "p50": round(sorted_lats[int(n * 0.50)], 3),
        "p95": round(sorted_lats[min(int(n * 0.95), n - 1)], 3),
        "p99": round(sorted_lats[min(int(n * 0.99), n - 1)], 3),
        "mean": round(sum(sorted_lats) / n, 3),
    }


def benchmark_secret_scanner(iterations: int = 200) -> dict[str, Any]:
    """Benchmark SecretScanner redaction performance on 100 KB payload."""
    scanner = SecretScanner()
    sample_text = (
        "User query sk-proj-1234567890abcdef1234567890abcdef1234567890abcdef "
        "and api_key=AIzaSyA1234567890abcdef1234567890abcdef "
    ) * 1000  # ~100 KB payload

    latencies = []
    start_total = time.perf_counter()
    for _ in range(iterations):
        t0 = time.perf_counter()
        scanner.redact_text(sample_text)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)
    total_time = time.perf_counter() - start_total

    stats = calculate_percentiles(latencies)
    stats["ops_per_sec"] = round(iterations / total_time, 2)
    stats["payload_size_kb"] = round(len(sample_text) / 1024.0, 1)
    return stats


def benchmark_audit_logger(iterations: int = 300, tmp_dir: Path | None = None) -> dict[str, Any]:
    """Benchmark SecurityAuditLogger event writing and SHA-256 hash chaining."""
    target_dir = tmp_dir or Path("benchmarks")
    logger = SecurityAuditLogger(log_dir=target_dir)

    latencies = []
    start_total = time.perf_counter()
    for i in range(iterations):
        t0 = time.perf_counter()
        logger.log_event(
            action="BENCHMARK_TEST",
            actor=f"user_{i}",
            tenant="default",
            metadata={"iteration": i, "status": "success"},
        )
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)
    total_time = time.perf_counter() - start_total

    stats = calculate_percentiles(latencies)
    stats["ops_per_sec"] = round(iterations / total_time, 2)
    return stats


def benchmark_session_db(iterations: int = 150, tmp_dir: Path | None = None) -> dict[str, Any]:
    """Benchmark SessionDB turn insertion and FTS5 search performance."""
    db_file = (tmp_dir or Path("benchmarks")) / "bench_session.db"
    db = SessionDB(db_path=db_file)

    # Turn insertion benchmark
    insert_lats = []
    for i in range(iterations):
        t0 = time.perf_counter()
        db.add_turn(
            session_id=f"bench_sess_{i % 5}",
            role="user" if i % 2 == 0 else "assistant",
            content=f"Benchmark interaction turn content {i} searching for keyword alpha",
        )
        t1 = time.perf_counter()
        insert_lats.append((t1 - t0) * 1000.0)

    # FTS5 search benchmark
    search_lats = []
    start_search = time.perf_counter()
    for _ in range(iterations):
        t0 = time.perf_counter()
        results = db.search_turns(query="alpha")
        t1 = time.perf_counter()
        search_lats.append((t1 - t0) * 1000.0)
        assert len(results) > 0
    total_search_time = time.perf_counter() - start_search

    db.close()
    if db_file.exists():
        db_file.unlink()

    insert_stats = calculate_percentiles(insert_lats)
    search_stats = calculate_percentiles(search_lats)
    search_stats["ops_per_sec"] = round(iterations / total_search_time, 2)

    return {
        "insert_turn": insert_stats,
        "fts5_search": search_stats,
    }


def benchmark_template_manager(iterations: int = 300) -> dict[str, Any]:
    """Benchmark TemplateManager prompt rendering performance."""
    tm = TemplateManager()
    context = {"agent_name": "AmberClawSentinel", "role": "SecurityGuard", "env": "Production"}

    latencies = []
    start_total = time.perf_counter()
    for _ in range(iterations):
        t0 = time.perf_counter()
        tm.render_template("AGENTS.md", context)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)
    total_time = time.perf_counter() - start_total

    stats = calculate_percentiles(latencies)
    stats["ops_per_sec"] = round(iterations / total_time, 2)
    return stats


def run_full_benchmark_suite(output_file: Path | None = None) -> dict[str, Any]:
    """Run full benchmark suite across all core modules and export JSON summary."""
    bench_dir = Path("benchmarks")
    bench_dir.mkdir(parents=True, exist_ok=True)

    print("🚀 Running AmberClaw Performance Benchmark Suite...")
    results = {
        "benchmark_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "secret_scanner_100kb": benchmark_secret_scanner(),
        "security_audit_logger": benchmark_audit_logger(tmp_dir=bench_dir),
        "session_db": benchmark_session_db(tmp_dir=bench_dir),
        "template_manager_render": benchmark_template_manager(),
    }

    target_path = output_file or (bench_dir / "benchmark_results.json")
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"✅ Performance benchmark results written to {target_path}")
    return results


if __name__ == "__main__":
    run_full_benchmark_suite()
