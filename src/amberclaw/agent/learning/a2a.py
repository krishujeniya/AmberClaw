"""Agent-to-Agent (A2A) execution module."""

from __future__ import annotations

import httpx
from loguru import logger

from amberclaw.bus.queue import MessageBus
from amberclaw.config import loader, paths
from amberclaw.cron.service import CronService
from amberclaw.providers import factory


async def execute_local_task(task: str, session_id: str = "a2a:direct") -> str:
    """Instantiates a local AgentLoop to execute a delegated task."""
    from amberclaw.agent.loop import AgentLoop  # noqa: PLC0415

    cfg = loader.load_runtime_config(None, None)
    bus = MessageBus()
    provider = factory.make_provider(cfg)
    cron_store_path = paths.get_cron_dir() / "jobs.json"
    cron = CronService(cron_store_path)

    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=cfg.workspace_path,
        model=cfg.agents.defaults.model,
        temperature=cfg.agents.defaults.temperature,
        max_tokens=cfg.agents.defaults.max_tokens,
        max_iterations=cfg.agents.defaults.max_tool_iterations,
        memory_window=cfg.agents.defaults.memory_window,
        reasoning_effort=cfg.agents.defaults.reasoning_effort,
        brave_api_key=cfg.tools.web.search.api_key or None,
        web_proxy=cfg.tools.web.proxy or None,
        exec_config=cfg.tools.exec,
        cron_service=cron,
        restrict_to_workspace=cfg.tools.restrict_to_workspace,
        mcp_servers=cfg.tools.mcp_servers,
        channels_config=cfg.channels,
        fallback_models=cfg.agents.defaults.fallback_models,
        embedding_model=cfg.agents.defaults.embedding_model,
        reranker_model=cfg.agents.defaults.reranker_model,
    )

    try:
        return await agent_loop.process_direct(
            text=task,
            session_id=session_id,
        )
    finally:
        await agent_loop.close_mcp()


async def delegate_to_remote(target_url: str, task: str) -> str:
    """Sends a JSON-RPC 2.0 request to execute a task on a remote agent."""
    payload = {
        "jsonrpc": "2.0",
        "method": "execute_task",
        "params": {
            "task": task,
        },
        "id": 1,
    }

    logger.info("A2A Client: Delegating task to remote agent at '{}'", target_url)

    async with httpx.AsyncClient() as client:
        response = await client.post(target_url, json=payload, timeout=60.0)
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            err = data["error"]
            raise RuntimeError(f"Remote agent returned error {err.get('code')}: {err.get('message')}")

        result = data.get("result", {})
        if isinstance(result, dict) and "output" in result:
            return result["output"]

        raise ValueError(f"Unexpected response format from remote agent: {data}")
