"""Local testing harness for AmberClaw Agent evaluations (AC-058)."""

import asyncio
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from loguru import logger

from amberclaw.agent.loop import AgentLoop
from amberclaw.bus.queue import MessageBus
from amberclaw.providers.litellm_provider import LiteLLMProvider


async def run_evaluation(prompt: str, expected_tool: str) -> dict[str, Any]:
    """Run one explicitly invoked model-backed case using the canonical agent API.

    Importing/collecting this module does not run evaluations. Calling this
    function uses the configured model and may execute tools.
    """
    provider = LiteLLMProvider(default_model="gpt-4o-mini")
    called_tools: set[str] = set()

    def record_execution(tool):
        original_execute = tool.execute

        async def execute(**kwargs):
            called_tools.add(tool.name)
            return await original_execute(**kwargs)

        return execute

    start_time = time.perf_counter()
    failure = None
    with TemporaryDirectory(prefix="amberclaw-eval-") as directory:
        agent = AgentLoop(
            provider=provider, workspace=Path(directory), bus=MessageBus()
        )
        for tool in agent.tools.values():
            tool.execute = record_execution(tool)
        try:
            await agent.process_direct(prompt, session_key="eval:case")
        except Exception as exc:
            failure = type(exc).__name__
            logger.error("Evaluation failed: {}", failure)
        finally:
            agent.stop()
            await agent.close_mcp()

    return {
        "prompt": prompt,
        "expected_tool": expected_tool,
        "called_tools": sorted(called_tools),
        "success": failure is None and expected_tool in called_tools,
        "latency_sec": round(time.perf_counter() - start_time, 3),
        "error": failure,
    }


async def run_suite():
    evals = [
        {
            "prompt": "Search the web for the capital of France.",
            "expected_tool": "web_search",
        },
        {"prompt": "Run a python script that prints hello.", "expected_tool": "exec"},
        {
            "prompt": "Navigate to https://example.com",
            "expected_tool": "browser_action",
        },
    ]

    results = []
    success_count = 0
    total_latency = 0.0

    logger.info(f"Starting evaluation suite with {len(evals)} test cases...")

    for case in evals:
        res = await run_evaluation(case["prompt"], case["expected_tool"])
        results.append(res)
        if res["success"]:
            success_count += 1
        total_latency += res["latency_sec"]
        logger.info(
            f"Eval: '{case['prompt'][:30]}...' -> Success: {res['success']} ({res['latency_sec']}s)"
        )

    accuracy = (success_count / len(evals)) * 100
    avg_latency = total_latency / len(evals)

    logger.info("=== EVALUATION RESULTS ===")
    logger.info(f"Accuracy: {accuracy:.1f}% ({success_count}/{len(evals)})")
    logger.info(f"Avg Latency: {avg_latency:.3f}s")

    return results


if __name__ == "__main__":
    asyncio.run(run_suite())
