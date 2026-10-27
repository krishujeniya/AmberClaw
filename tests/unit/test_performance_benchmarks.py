from benchmarks.benchmark_suite import (
    benchmark_audit_logger,
    benchmark_secret_scanner,
    benchmark_session_db,
    benchmark_template_manager,
    run_full_benchmark_suite,
)


def test_secret_scanner_performance_budget():
    stats = benchmark_secret_scanner(iterations=50)
    assert stats["p50"] < 15.0  # p50 latency under 15 ms per 100 KB
    assert stats["ops_per_sec"] > 50.0  # throughput over 50 ops/sec


def test_audit_logger_performance_budget(tmp_path):
    stats = benchmark_audit_logger(iterations=50, tmp_dir=tmp_path)
    assert stats["p50"] < 10.0  # p50 write latency under 10 ms
    assert stats["ops_per_sec"] > 100.0


def test_session_db_performance_budget(tmp_path):
    stats = benchmark_session_db(iterations=30, tmp_dir=tmp_path)
    assert stats["fts5_search"]["p50"] < 25.0  # FTS5 search p50 under 25 ms
    assert stats["insert_turn"]["p50"] < 200.0  # Turn insertion p50 under 200 ms


def test_template_manager_performance_budget():
    stats = benchmark_template_manager(iterations=50)
    assert stats["p50"] < 5.0  # p50 latency under 5 ms
    assert stats["ops_per_sec"] > 200.0


def test_full_benchmark_suite_json_export(tmp_path):
    out_file = tmp_path / "test_bench_out.json"
    res = run_full_benchmark_suite(output_file=out_file)
    assert out_file.exists()
    assert "secret_scanner_100kb" in res
    assert "security_audit_logger" in res
    assert "session_db" in res
    assert "template_manager_render" in res
