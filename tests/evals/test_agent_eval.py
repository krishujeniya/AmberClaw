"""Local testing harness for AmberClaw Agent evaluations (AC-058)."""

import asyncio
import time
from typing import Any

from loguru import logger

from amberclaw.agent.loop import AgentLoop
from amberclaw.providers.litellm_provider import LiteLLMProvider


async def run_evaluation(prompt: str, expected_tool: str) -> dict[str, Any]:
    """Run a single evaluation task and check if the expected tool was called."""
    provider = LiteLLMProvider(model="gpt-4o-mini")  # Replace with appropriate test model
    # Mock bus for testing
    
    class MockBus:
        def publish_outbound(self, msg): pass
        def publish_system(self, msg): pass
        def publish_developer(self, msg): pass
        def publish_error(self, msg): pass

    agent = AgentLoop(
        provider=provider,
        workspace="/tmp/amberclaw_eval",
        bus=MockBus()
    )
    
    # We will track which tools get called by patching the tools or checking the graph state
    called_tools = set()
    
    # Simple wrapper to record tool calls
    for tool_name, tool in agent.tools.items():
        original_execute = tool.execute
        
        async def mock_execute(args, name=tool_name, orig=original_execute):
            called_tools.add(name)
            return await orig(args)
            
        tool.execute = mock_execute

    start_time = time.time()
    
    try:
        await agent.start(session_id="eval_session")
        # Run a single turn
        # The agent loop usually runs via send_message, which adds to a queue.
        # For evaluation, we can directly invoke the graph.
        
        messages = [{"role": "user", "content": prompt}]
        state = {"messages": messages, "mode": "react"}
        
        result = await agent._graph.graph.ainvoke(state)
        
    except Exception as e:
        logger.error(f"Eval failed: {e}")
    finally:
        latency = time.time() - start_time
        await agent.stop()
        
    # In LangGraph, tool calls are recorded in the messages
    for msg in result.get("messages", []):
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                called_tools.add(tc.get("name") if isinstance(tc, dict) else tc.name)

    success = expected_tool in called_tools
    
    return {
        "prompt": prompt,
        "expected_tool": expected_tool,
        "called_tools": list(called_tools),
        "success": success,
        "latency_sec": round(latency, 3),
    }

async def run_suite():
    evals = [
        {"prompt": "Search the web for the capital of France.", "expected_tool": "web_search"},
        {"prompt": "Run a python script that prints hello.", "expected_tool": "exec"},
        {"prompt": "Navigate to https://example.com", "expected_tool": "browser_action"},
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
        logger.info(f"Eval: '{case['prompt'][:30]}...' -> Success: {res['success']} ({res['latency_sec']}s)")
        
    accuracy = (success_count / len(evals)) * 100
    avg_latency = total_latency / len(evals)
    
    logger.info("=== EVALUATION RESULTS ===")
    logger.info(f"Accuracy: {accuracy:.1f}% ({success_count}/{len(evals)})")
    logger.info(f"Avg Latency: {avg_latency:.3f}s")
    
    return results

if __name__ == "__main__":
    asyncio.run(run_suite())
