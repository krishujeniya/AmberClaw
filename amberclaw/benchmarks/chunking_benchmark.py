"""Multi-Format Document Chunking Benchmark Suite for AmberClaw.

Measures chunking performance, chunk count, size variance, and throughput (KB/s)
across Markdown, Python Code, Plain Text, and HTML document types.
"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from amberclaw.memory.rag_pipeline import DocumentIngestor, HTMLToTextConverter

console = Console()


# ==============================================================================
# Sample Multi-Format Document Payloads (~20-50 KB each)
# ==============================================================================
SAMPLE_MARKDOWN = (
    """
# System Architecture Specification: AmberClaw OS

## 1. Overview
AmberClaw is an autonomous agent operating system kernel featuring:
- Hardware-enforced isolation via Linux seccomp and Landlock.
- Multi-tier memory architecture (SQLite SessionDB, ChromaDB vector store, Mem0).
- Zero-trust communication bus with priority scheduling and dead-letter queues.

## 2. Core Kernel Components

### 2.1 Message Bus
The bus coordinates asynchronous messaging across agent processes.
It supports:
1. Inbound queueing with backpressure controls.
2. Outbound multiplexing to channels (CLI, Discord, Telegram, Webhook).
3. System event dispatching for lifecycle monitoring.

### 2.2 Memory System
The memory subsystem manages short-term conversational context and long-term knowledge.
- **Short-term Memory**: SQLite WAL transactions with FTS5 indexed search.
- **Long-term Memory**: Dense vector similarity search with BM25 hybrid ranking.
- **Consolidation**: Background task running consolidation passes to prune context.

## 3. Governance and Security Rules
Every agent action is evaluated by the Governance Engine before execution:
```json
{
  "policy": "enforce_rate_limits",
  "max_ops_per_minute": 120,
  "action": "ALLOW"
}
```
"""
    * 15
)

SAMPLE_PYTHON_CODE = (
    '''
"""Core worker and dispatcher implementation for distributed tasks."""

import asyncio
from typing import Any, Callable


class TaskDispatcher:
    """Dispatches background tasks to isolated worker pools."""

    def __init__(self, pool_size: int = 8) -> None:
        self.pool_size = pool_size
        self.queue: asyncio.Queue[tuple[str, Callable[..., Any]]] = asyncio.Queue()
        self.active_workers: list[asyncio.Task] = []

    async def start(self) -> None:
        for idx in range(self.pool_size):
            worker = asyncio.create_task(self._worker_loop(idx))
            self.active_workers.append(worker)

    async def _worker_loop(self, worker_id: int) -> None:
        while True:
            task_id, fn = await self.queue.get()
            try:
                result = await fn() if asyncio.iscoroutinefunction(fn) else fn()
            except Exception as e:
                pass
            finally:
                self.queue.task_done()

    async def submit(self, task_id: str, fn: Callable[..., Any]) -> None:
        await self.queue.put((task_id, fn))
'''
    * 20
)

SAMPLE_PLAIN_TEXT = (
    """
[SESSION LOG - 2026-09-23T10:00:00Z]
User: Please summarize the quarterly performance metrics for the deployment fleet.
Assistant: Reviewing cluster metrics across all availability zones.
Cluster us-east-1 reports 99.98% uptime with an average response latency of 42ms.
Cluster eu-west-1 reports 100.0% uptime with average response latency of 38ms.
User: Did any security alerts trigger in the last 24 hours?
Assistant: Zero high-severity alerts detected. Two benign port scans were blocked at the firewall.
User: Excellent, please archive this session report into memory.
Assistant: Report archived to SessionDB under session identifier fleet_report_q3.
"""
    * 30
)

SAMPLE_HTML = (
    """
<!DOCTYPE html>
<html>
<head><title>System Health Status</title></head>
<body>
  <h1>AmberClaw Infrastructure Monitor</h1>
  <div class="metrics-grid">
    <p>Database connection pool: Healthy (48/50 connections active).</p>
    <p>Message queue depth: 12 messages pending in inbound buffer.</p>
    <p>Vector storage index: 1,420 document chunks indexed.</p>
  </div>
  <table>
    <thead><tr><th>Node</th><th>Status</th><th>CPU</th><th>Memory</th></tr></thead>
    <tbody>
      <tr><td>node-01</td><td>ONLINE</td><td>14.2%</td><td>4.1 GB</td></tr>
      <tr><td>node-02</td><td>ONLINE</td><td>18.5%</td><td>5.2 GB</td></tr>
    </tbody>
  </table>
</body>
</html>
"""
    * 20
)


def benchmark_document_type(
    doc_type: str,
    content: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> dict[str, Any]:
    """Run chunking benchmark on specific document type."""
    ingestor = DocumentIngestor(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    # If HTML, measure conversion + chunking
    t0 = time.perf_counter()
    if doc_type == "html":
        conv = HTMLToTextConverter()
        conv.feed(content)
        cleaned_text = conv.get_text()
        docs = ingestor.load_text(cleaned_text, source="bench.html")
    else:
        docs = ingestor.load_text(content, source=f"bench.{doc_type}")
    duration = time.perf_counter() - t0

    payload_bytes = len(content.encode("utf-8"))
    payload_kb = payload_bytes / 1024.0
    throughput_kb_s = round(payload_kb / duration, 2) if duration > 0 else 0.0

    chunk_lengths = [len(d.page_content) for d in docs]
    mean_chunk_len = round(statistics.mean(chunk_lengths), 1) if chunk_lengths else 0.0
    stdev_chunk_len = (
        round(statistics.stdev(chunk_lengths), 1) if len(chunk_lengths) > 1 else 0.0
    )

    # Rough token estimation (~4 chars/token)
    estimated_tokens = [len(d.page_content.split()) for d in docs]
    mean_tokens = (
        round(statistics.mean(estimated_tokens), 1) if estimated_tokens else 0.0
    )

    return {
        "doc_type": doc_type,
        "payload_kb": round(payload_kb, 2),
        "chunk_count": len(docs),
        "duration_ms": round(duration * 1000.0, 2),
        "throughput_kb_s": throughput_kb_s,
        "mean_chunk_chars": mean_chunk_len,
        "stdev_chunk_chars": stdev_chunk_len,
        "mean_tokens_per_chunk": mean_tokens,
    }


def run_chunking_benchmarks(output_file: Path | None = None) -> dict[str, Any]:
    """Execute chunking benchmarks across Markdown, Python, Text, and HTML."""
    payloads = {
        "markdown": SAMPLE_MARKDOWN,
        "python_code": SAMPLE_PYTHON_CODE,
        "plain_text": SAMPLE_PLAIN_TEXT,
        "html": SAMPLE_HTML,
    }

    results: dict[str, Any] = {}
    table = Table(title="Document Chunking Benchmarks by Document Type")
    table.add_column("Type", style="cyan")
    table.add_column("Payload (KB)", justify="right")
    table.add_column("Chunks", justify="right")
    table.add_column("Duration (ms)", justify="right")
    table.add_column("Throughput (KB/s)", style="green", justify="right")
    table.add_column("Avg Chunk Chars", justify="right")
    table.add_column("Avg Tokens/Chunk", justify="right")

    for doc_type, payload in payloads.items():
        res = benchmark_document_type(doc_type, payload)
        results[doc_type] = res
        table.add_row(
            doc_type,
            f"{res['payload_kb']:.1f}",
            str(res["chunk_count"]),
            f"{res['duration_ms']:.2f}",
            f"{res['throughput_kb_s']:.1f}",
            f"{res['mean_chunk_chars']:.0f}",
            f"{res['mean_tokens_per_chunk']:.0f}",
        )

    console.print(table)

    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open("w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        console.print(
            f"[green]Chunking benchmark results saved to {output_file}[/green]"
        )

    return results


if __name__ == "__main__":
    out = Path("benchmarks/chunking_benchmark_results.json")
    run_chunking_benchmarks(output_file=out)
