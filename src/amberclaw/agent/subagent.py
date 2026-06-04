"""Subagent manager for background task execution."""

import asyncio
import uuid
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from amberclaw.agent.graph import AgentGraph, AgentState
from amberclaw.agent.tools.filesystem import (
    EditFileTool,
    ListDirTool,
    ReadFileTool,
    WriteFileTool,
)
from amberclaw.agent.tools.registry import ToolRegistry
from amberclaw.agent.tools.shell import ExecTool
from amberclaw.agent.tools.web import WebFetchTool, WebSearchTool
from amberclaw.bus.events import InboundMessage
from amberclaw.bus.queue import MessageBus
from amberclaw.config.schema import ExecToolConfig
from amberclaw.providers.base import LLMProvider


class SubagentManager:
    """Manages background subagent execution."""

    def __init__(  # noqa: PLR0913
        self,
        provider: LLMProvider,
        workspace: Path,
        bus: MessageBus,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        reasoning_effort: str | None = None,
        brave_api_key: str | None = None,
        web_proxy: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
        restrict_to_workspace: bool = False,
    ):
        from amberclaw.config.schema import ExecToolConfig  # noqa: PLC0415

        self.provider = provider
        self.workspace = workspace
        self.bus = bus
        self.model = model or provider.get_default_model()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort
        self.brave_api_key = brave_api_key
        self.web_proxy = web_proxy
        self.exec_config = exec_config or ExecToolConfig()
        self.restrict_to_workspace = restrict_to_workspace
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
        self._session_tasks: dict[str, set[str]] = {}  # session_key -> {task_id, ...}

    async def spawn(  # noqa: PLR0913
        self,
        task: str,
        label: str | None = None,
        origin_channel: str = "cli",
        origin_chat_id: str = "direct",
        session_key: str | None = None,
        model: str | None = None,
        reasoning_effort: str | None = None,
        worker_role: str | None = None,
    ) -> str:
        """Spawn a subagent to execute a task in the background."""
        task_id = str(uuid.uuid4())[:8]
        display_label = label or task[:30] + ("..." if len(task) > 30 else "")  # noqa: PLR2004
        origin = {"channel": origin_channel, "chat_id": origin_chat_id}

        bg_task = asyncio.create_task(
            self._run_subagent(
                task_id,
                task,
                display_label,
                origin,
                model=model,
                reasoning_effort=reasoning_effort,
                worker_role=worker_role,
            ),
        )
        self._running_tasks[task_id] = bg_task
        if session_key:
            self._session_tasks.setdefault(session_key, set()).add(task_id)

        def _cleanup(_: asyncio.Task) -> None:
            self._running_tasks.pop(task_id, None)
            if session_key and (ids := self._session_tasks.get(session_key)):
                ids.discard(task_id)
                if not ids:
                    del self._session_tasks[session_key]

        bg_task.add_done_callback(_cleanup)

        logger.info("Spawned subagent [{}]: {}", task_id, display_label)
        return f"Subagent [{display_label}] started (id: {task_id}). I'll notify you when it completes."

    async def _run_subagent(  # noqa: PLR0913
        self,
        task_id: str,
        task: str,
        label: str,
        origin: dict[str, str],
        model: str | None = None,
        reasoning_effort: str | None = None,
        worker_role: str | None = None,
    ) -> None:
        """Execute the subagent task and announce the result."""
        logger.info("Subagent [{}] starting task: {}", task_id, label)

        try:
            # Build subagent tools (no message tool, no spawn tool)
            tools = ToolRegistry()
            allowed_dir = self.workspace if self.restrict_to_workspace else None

            # Role-based tool access restriction
            role = (worker_role or "general").lower()

            # Define tool permissions
            has_files = role in ("coder", "general", "researcher", "reader")
            has_write = role in ("coder", "general")
            has_exec = role in ("coder", "general")
            has_web = role in ("researcher", "general")

            if has_files:
                tools.register(ReadFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
                tools.register(ListDirTool(workspace=self.workspace, allowed_dir=allowed_dir))
                if has_write:
                    tools.register(WriteFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
                    tools.register(EditFileTool(workspace=self.workspace, allowed_dir=allowed_dir))

            if has_exec:
                tools.register(
                    ExecTool(
                        working_dir=str(self.workspace),
                        timeout=self.exec_config.timeout,
                        restrict_to_workspace=self.restrict_to_workspace,
                        path_append=self.exec_config.path_append,
                    ),
                )

            if has_web:
                tools.register(WebSearchTool(api_key=self.brave_api_key, proxy=self.web_proxy))
                tools.register(WebFetchTool(proxy=self.web_proxy))

            system_prompt = self._build_subagent_prompt(role)
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=task),
            ]

            # Use LangGraph instead of a while loop for subagents (AC-054)
            graph = AgentGraph(
                provider=self.provider,
                tools=list(tools.values()),
                max_iterations=15,
                mode="react",
            )

            inputs = {
                "messages": messages,
                "iterations": 0,
                "mode": "react",
                "plan": [],
                "current_task": None,
                "config": {
                    "model": model or self.model,
                    "llm_kwargs": {
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens,
                        "reasoning_effort": reasoning_effort or self.reasoning_effort,
                    },
                },
            }

            from typing import cast  # noqa: PLC0415
            final_state = await graph.runnable.ainvoke(cast(AgentState, inputs))
            final_msg = final_state["messages"][-1]
            final_result = str(final_msg.content) if final_msg.content else None

            if final_result is None:
                final_result = "Task completed but no final response was generated."

            logger.info("Subagent [{}] completed successfully", task_id)
            await self._announce_result(task_id, label, task, final_result, origin, "ok")

        except Exception as e:
            error_msg = f"Error: {e!s}"
            logger.error("Subagent [{}] failed: {}", task_id, e)
            await self._announce_result(task_id, label, task, error_msg, origin, "error")

    async def _announce_result(  # noqa: PLR0913
        self,
        task_id: str,
        label: str,
        task: str,
        result: str,
        origin: dict[str, str],
        status: str,
    ) -> None:
        """Announce the subagent result to the main agent via the message bus."""
        status_text = "completed successfully" if status == "ok" else "failed"

        announce_content = f"""[Subagent '{label}' {status_text}]

Task: {task}

Result:
{result}

Summarize this naturally for the user. Keep it brief (1-2 sentences). Do not mention technical details like "subagent" or task IDs."""

        # Inject as system message to trigger main agent
        msg = InboundMessage(
            channel="system",
            sender_id="subagent",
            chat_id=f"{origin['channel']}:{origin['chat_id']}",
            content=announce_content,
        )

        await self.bus.publish_inbound(msg)
        logger.debug(
            "Subagent [{}] announced result to {}:{}", task_id, origin["channel"], origin["chat_id"],
        )

    def _build_subagent_prompt(self, role: str = "general") -> str:
        """Build a focused system prompt for the subagent."""
        from amberclaw.agent.context import ContextBuilder  # noqa: PLC0415
        from amberclaw.agent.skills import SkillsLoader  # noqa: PLC0415

        time_ctx = ContextBuilder._build_runtime_context(None, None)

        role_instructions = {
            "coder": "You are a Coder specialized worker agent. Your primary role is to read, write, edit, and execute code within the workspace.",
            "researcher": "You are a Researcher specialized worker agent. Your primary role is to perform web search and fetch resources to answer complex queries. You do not have write or execution permissions.",
            "reader": "You are a Reader specialized worker agent. Your primary role is to inspect the directory structure and read file contents. You are run in a safe, read-only mode.",
            "general": "You are a General worker agent. You have access to all tools to complete the task.",
        }
        role_prompt = role_instructions.get(role, role_instructions["general"])

        parts = [
            f"""# Subagent

Role: {role.upper()}
{role_prompt}

{time_ctx}

You are a subagent spawned by the main agent to complete a specific task.
Stay focused on the assigned task. Your final response will be reported back to the main agent.

## Workspace
{self.workspace}""",
        ]

        skills_summary = SkillsLoader(self.workspace).build_skills_summary()
        if skills_summary:
            parts.append(
                f"## Skills\n\nRead SKILL.md with read_file to use a skill.\n\n{skills_summary}",
            )

        return "\n\n".join(parts)

    async def cancel_by_session(self, session_key: str) -> int:
        """Cancel all subagents for the given session. Returns count cancelled."""
        tasks = [
            self._running_tasks[tid]
            for tid in self._session_tasks.get(session_key, [])
            if tid in self._running_tasks and not self._running_tasks[tid].done()
        ]
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        return len(tasks)

    def get_running_count(self) -> int:
        """Return the number of currently running subagents."""
        return len(self._running_tasks)
