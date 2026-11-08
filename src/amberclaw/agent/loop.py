"""Agent loop: the core processing engine."""

from __future__ import annotations

import asyncio
import json as _json
import re
import weakref
from collections.abc import Awaitable, Callable, Coroutine, Sequence
from contextlib import AsyncExitStack, suppress
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from loguru import logger

from amberclaw.agent.a2a import A2AManager, AgentCard
from amberclaw.agent.context import ContextBuilder
from amberclaw.agent.graph import AgentGraph, AgentState
from amberclaw.agent.memory import MemoryStore
from amberclaw.agent.subagent import SubagentManager
from amberclaw.agent.token_counter import count_tokens
from amberclaw.agent.tools.a2a import A2ADelegateTool
from amberclaw.agent.tools.council import CouncilTool
from amberclaw.agent.tools.cron import CronTool
from amberclaw.agent.tools.data_clean import DataCleanTool
from amberclaw.agent.tools.data_eda import DataEDATool
from amberclaw.agent.tools.data_sql import DataSQLTool
from amberclaw.agent.tools.data_viz import DataVizTool
from amberclaw.agent.tools.drive import DriveSearchTool, DriveUploadTool
from amberclaw.agent.tools.filesystem import (
    EditFileTool,
    ListDirTool,
    ReadFileTool,
    WriteFileTool,
)
from amberclaw.agent.tools.gui import BrowserActionTool, DesktopAutomationTool
from amberclaw.agent.tools.message import MessageTool
from amberclaw.agent.tools.multimodal import (
    DocumentIngestionTool,
    SensorInputTool,
    TranscriptionTool,
    TTSTool,
    VideoAnalysisTool,
    VisionTool,
)
from amberclaw.agent.tools.mythos import MythosTool
from amberclaw.agent.tools.personal_assistant import AssistantTool
from amberclaw.agent.tools.personal_rag import KnowledgeAddTool, KnowledgeSearchTool
from amberclaw.agent.tools.registry import ToolRegistry
from amberclaw.agent.tools.shell import ExecTool
from amberclaw.agent.tools.skills import (
    SkillInstallTool,
    SkillListTool,
    SkillManageTool,
    SkillSearchTool,
)
from amberclaw.agent.tools.spawn import SpawnTool
from amberclaw.agent.tools.web import WebFetchTool, WebSearchTool
from amberclaw.bus.events import InboundMessage, OutboundMessage
from amberclaw.bus.queue import MessageBus
from amberclaw.config.schema import Config
from amberclaw.providers.base import LLMProvider
from amberclaw.session.manager import Session, SessionManager

TOOL_ARGUMENT_PREVIEW_CHARS = 40
PAIR_COMMAND_PARTS = 2
INBOUND_LOG_PREVIEW_CHARS = 80
OUTBOUND_LOG_PREVIEW_CHARS = 120


if TYPE_CHECKING:
    from amberclaw.config.schema import ChannelsConfig, ExecToolConfig
    from amberclaw.cron.service import CronService


_WorkResult = TypeVar("_WorkResult")


class AgentLoop:
    """
    The agent loop is the core processing engine.

    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """

    _TOOL_RESULT_MAX_CHARS = 500

    def __init__(  # noqa: PLR0913 - preserve the public agent configuration constructor
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 40,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        memory_window: int = 100,
        mode: str = "react",
        reasoning_effort: str | None = None,
        brave_api_key: str | None = None,
        web_proxy: str | None = None,
        exec_config: ExecToolConfig | None = None,
        cron_service: CronService | None = None,
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
        mcp_servers: dict[str, Any] | None = None,
        channels_config: ChannelsConfig | None = None,
        fallback_models: list[str] | None = None,
        embedding_model: str | None = None,
        reranker_model: str | None = None,
    ) -> None:
        from amberclaw.config.schema import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
            ExecToolConfig,
        )

        self.bus = bus
        self.channels_config = channels_config
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.mode = mode
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.memory_window = memory_window
        self.reasoning_effort = reasoning_effort
        self.brave_api_key = brave_api_key
        self.web_proxy = web_proxy
        self.exec_config = exec_config or ExecToolConfig()
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace
        self.fallback_models = fallback_models or []
        from amberclaw.security.pii import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
            PIIRedactor,
        )

        self.pii_redactor = PIIRedactor()
        self.embedding_model = embedding_model
        self.reranker_model = reranker_model

        self.context = ContextBuilder(workspace)
        self.sessions = session_manager or SessionManager(workspace)
        self.tools = ToolRegistry()
        from amberclaw.plugins.manager import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
            PluginManager,
        )

        self.plugin_manager = PluginManager(workspace=self.workspace)
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            reasoning_effort=reasoning_effort,
            brave_api_key=brave_api_key,
            web_proxy=web_proxy,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
        )

        self._running = False
        self._closing = False
        self._plugin_stop_task: asyncio.Task[None] | None = None
        self._mcp_servers = mcp_servers or {}
        self._mcp_discovery_task: asyncio.Task[Any] | None = None

        # Initialize A2A
        self.a2a_manager = A2AManager(
            AgentCard(
                name="AmberClaw",
                capabilities=["rag", "data", "web", "mcp"],
                endpoints={
                    "a2a": getattr(channels_config, "a2a_url", "")
                    if channels_config
                    else ""
                },
            ),
        )

        self._mcp_stack: AsyncExitStack | None = None
        self._mcp_connected = False
        self._mcp_connecting = False
        self._consolidating: set[str] = (
            set()
        )  # Session keys with consolidation in progress
        self._consolidation_tasks: set[asyncio.Task[Any]] = (
            set()
        )  # Strong refs to in-flight tasks
        self._consolidation_locks: weakref.WeakValueDictionary[str, asyncio.Lock] = (
            weakref.WeakValueDictionary()
        )
        self._active_tasks: dict[
            str, list[asyncio.Task[Any]]
        ] = {}  # session_key -> tasks
        self._processing_lock = asyncio.Lock()

        # Register tools first so AgentGraph ToolNode has the full tool set
        self._register_default_tools()

        # Initialize LangGraph engine with fully populated tools
        self._graph = AgentGraph(
            provider=self.provider,
            tools=list(self.tools.values()),
            max_iterations=self.max_iterations,
            mode=self.mode,
        )

    def _register_default_tools(self) -> None:
        """Register all core tools — every feature is always available from user config."""
        from amberclaw.config.loader import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
            load_config,
        )

        _cfg = load_config()

        allowed_dir = self.workspace if self.restrict_to_workspace else None

        # ── Filesystem ────────────────────────────────────────────────────────
        for cls in (ReadFileTool, WriteFileTool, EditFileTool, ListDirTool):
            self.tools.register(cls(workspace=self.workspace, allowed_dir=allowed_dir))

        # ── Shell ─────────────────────────────────────────────────────────────
        self.tools.register(
            ExecTool(
                working_dir=str(self.workspace),
                timeout=self.exec_config.timeout,
                restrict_to_workspace=self.restrict_to_workspace,
                path_append=self.exec_config.path_append,
            ),
        )

        # ── Web ───────────────────────────────────────────────────────────────
        self.tools.register(
            WebSearchTool(api_key=self.brave_api_key, proxy=self.web_proxy)
        )
        self.tools.register(WebFetchTool(proxy=self.web_proxy))
        self.tools.register(BrowserActionTool())
        self.tools.register(DesktopAutomationTool())

        # ── Skills ────────────────────────────────────────────────────────────
        self.tools.register(SkillSearchTool())
        self.tools.register(
            SkillInstallTool(
                workspace=str(self.workspace),
                loader=self.context.skills,
            ),
        )
        self.tools.register(SkillListTool(workspace=str(self.workspace)))
        self.tools.register(SkillManageTool(workspace=str(self.workspace)))

        # ── Messaging / Scheduling ────────────────────────────────────────────
        async def _send_outbound_redacted(out_msg: OutboundMessage) -> None:
            from amberclaw.config.schema import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
                settings,
            )

            if settings.security.pii_redaction:
                out_msg.content = self.pii_redactor.redact(out_msg.content)
            await self.bus.publish_outbound(out_msg)

        self.tools.register(MessageTool(send_callback=_send_outbound_redacted))
        self.tools.register(SpawnTool(manager=self.subagents))
        self.tools.register(A2ADelegateTool())
        if self.cron_service:
            self.tools.register(CronTool(self.cron_service))

        self._register_optional_tools(_cfg)

    def _register_optional_tools(self, _cfg: Config) -> None:
        """Register optional integrations in their existing best-effort order."""
        # ── Council (multi-model consensus) — always core ─────────────────────
        try:
            self.tools.register(
                CouncilTool(
                    provider=self.provider,
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=min(self.max_tokens, 2048),
                ),
            )
            logger.info("Council tool registered")
        except Exception as exc:
            logger.debug("Council tool skipped: {}", exc)

        # ── Mythos (recursive deep reasoning) — always core ───────────────────
        try:
            self.tools.register(
                MythosTool(
                    provider=self.provider,
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=min(self.max_tokens, 2048),
                ),
            )
            logger.info("Mythos tool registered")
        except Exception as exc:
            logger.debug("Mythos tool skipped: {}", exc)

        # ── Personal Assistant (session-persisted conversation) ───────────────
        try:
            system_prompt = getattr(_cfg.assistant, "system_prompt", "") or ""
            self.tools.register(
                AssistantTool(
                    provider=self.provider,
                    model=self.model,
                    workspace=self.workspace,
                    temperature=0.7,
                    max_tokens=min(self.max_tokens, 2048),
                    system_prompt=system_prompt,
                ),
            )
            logger.info("PersonalAssistant tool registered")
        except Exception as exc:
            logger.debug("PersonalAssistant tool skipped: {}", exc)

        # ── Knowledge RAG ─────────────────────────────────────────────────────
        try:
            self.tools.register(
                KnowledgeSearchTool(
                    workspace=self.workspace,
                    provider=self.provider,
                    embedding_model=self.embedding_model
                    or "openai/text-embedding-3-small",
                    reranker_model=self.reranker_model,
                ),
            )
            self.tools.register(
                KnowledgeAddTool(
                    workspace=self.workspace,
                    provider=self.provider,
                    embedding_model=self.embedding_model
                    or "openai/text-embedding-3-small",
                ),
            )
            logger.info("Knowledge RAG tools registered")
        except Exception as exc:
            logger.debug("Knowledge RAG skipped: {}", exc)

        # ── Google Drive (optional — enabled in config) ───────────────────────
        try:
            if _cfg.tools.drive.enabled:
                self.tools.register(DriveSearchTool())
                self.tools.register(DriveUploadTool())
                logger.info("Drive tools registered")
        except Exception as exc:
            logger.debug("Drive tools skipped: {}", exc)

        self._register_multimodal_tools(_cfg)

    def _register_multimodal_tools(self, _cfg: Config) -> None:
        """Register multimodal, data, and A2A tools after the personal integrations."""
        # ── Multimodal (Vision, Audio, Video, Sensors) ────────────────────────
        try:
            self.tools.register(VisionTool(provider=self.provider))
            self.tools.register(TranscriptionTool())
            self.tools.register(TTSTool())
            self.tools.register(DocumentIngestionTool())
            self.tools.register(VideoAnalysisTool(provider=self.provider))
            self.tools.register(SensorInputTool())
            logger.info("Multimodal tools registered")
        except Exception as exc:
            logger.error("Multimodal tools failed to register: {}", exc)

        # ── DataAgent (data science suite) — always core ──────────────────────

        try:
            data_cfg = getattr(_cfg, "data", None)
            out_dir = getattr(data_cfg, "output_dir", None) if data_cfg else None
            lc_model = self.provider.to_langchain_chat(self.model, temperature=0.1)
            self.tools.register(DataCleanTool(output_dir=out_dir, model=lc_model))
            self.tools.register(DataVizTool(model=lc_model))
            self.tools.register(DataSQLTool(model=lc_model))
            self.tools.register(DataEDATool(model=lc_model))
            logger.info("DataAgent tools registered")

        except Exception as exc:
            logger.debug("DataAgent tools skipped: {}", exc)

        # ── A2A (Agent-to-Agent) ──────────────────────────────────────────────
        from amberclaw.agent.tools.a2a import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
            A2ADiscoveryTool,
            A2ATool,
        )

        self.tools.register(A2ATool(self.a2a_manager))
        self.tools.register(A2ADiscoveryTool(self.a2a_manager))
        logger.info("A2A tools registered")

    async def _connect_mcp(self) -> None:
        """Connect to configured MCP servers (one-time, lazy)."""
        if self._mcp_connected or self._mcp_connecting or not self._mcp_servers:
            return
        self._mcp_connecting = True
        from amberclaw.agent.tools.mcp import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
            connect_mcp_servers,
        )

        try:
            self._mcp_stack = AsyncExitStack()
            await self._mcp_stack.__aenter__()
            await connect_mcp_servers(self._mcp_servers, self.tools, self._mcp_stack)
            self._mcp_connected = True
        except Exception as e:
            logger.error(
                "Failed to connect MCP servers (will retry next message): {}", e
            )
            if self._mcp_stack:
                with suppress(Exception):
                    await self._mcp_stack.aclose()
                self._mcp_stack = None
        finally:
            self._mcp_connecting = False

    async def _mcp_discovery_loop(self) -> None:
        """Periodically scan for new MCP servers."""
        from amberclaw.agent.tools.mcp import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
            connect_mcp_servers,
        )

        while self._running:
            try:
                # Only discover if specifically requested or on local network
                # For now, we scan configured discovery URLs
                discovery_servers = {}
                for name, cfg in self._mcp_servers.items():
                    if getattr(cfg, "discover", False) and cfg.url:
                        discovery_servers[name] = cfg

                if discovery_servers and self._mcp_stack:
                    logger.debug("Running dynamic MCP discovery...")
                    await connect_mcp_servers(
                        discovery_servers, self.tools, self._mcp_stack
                    )
            except Exception as e:
                logger.error("Dynamic MCP discovery failed: {}", e)

            await asyncio.sleep(300)  # Scan every 5 minutes

    def _set_tool_context(
        self, channel: str, chat_id: str, message_id: str | None = None
    ) -> None:
        """Update context for all tools that need routing info."""
        for name in ("message", "spawn", "cron"):
            if (tool := self.tools.get(name)) and hasattr(tool, "set_context"):
                set_context = tool.set_context
                set_context(
                    channel, chat_id, *([message_id] if name == "message" else [])
                )

    @staticmethod
    def _strip_think(text: str | None) -> str | None:
        """Remove <think>…</think> blocks that some models embed in content."""
        if not text:
            return None
        return re.sub(r"<think>[\s\S]*?</think>", "", text).strip() or None

    @staticmethod
    def _tool_hint(tool_calls: list[Any]) -> str:
        """Format tool calls as concise hint, e.g. 'web_search("query")'."""

        def _fmt(tc: Any) -> str:
            args = (
                tc.arguments[0] if isinstance(tc.arguments, list) else tc.arguments
            ) or {}
            val = next(iter(args.values()), None) if isinstance(args, dict) else None
            if not isinstance(val, str):
                return str(tc.name)
            return (
                f'{tc.name}("{val[:40]}…")'
                if len(val) > TOOL_ARGUMENT_PREVIEW_CHARS
                else f'{tc.name}("{val}")'
            )

        return ", ".join(_fmt(tc) for tc in tool_calls)

    @staticmethod
    def _to_graph_messages(initial_messages: list[dict[Any, Any]]) -> list[BaseMessage]:
        """Preserve user, assistant, and tool messages at the graph boundary."""
        lc_msgs: list[BaseMessage] = []
        for m in initial_messages:
            role = m.get("role")
            content = m.get("content")
            if role == "user":
                lc_msgs.append(HumanMessage(content=content or ""))
            elif role == "assistant":
                ai_m = AIMessage(content=content or "")
                if m.get("tool_calls"):
                    ai_m.additional_kwargs["tool_calls"] = m["tool_calls"]
                if m.get("scratch_pad"):
                    ai_m.additional_kwargs["scratch_pad"] = m["scratch_pad"]
                lc_msgs.append(ai_m)
            elif role == "tool":
                lc_msgs.append(
                    ToolMessage(
                        content=content or "", tool_call_id=m.get("tool_call_id") or ""
                    ),
                )

        return lc_msgs

    @staticmethod
    def _from_graph_messages(messages: Sequence[BaseMessage]) -> list[dict[str, Any]]:
        """Keep the persisted assistant and tool metadata used by sessions."""
        # Back-convert to list[dict] for AmberClaw session storage
        all_msgs_dict: list[dict[str, Any]] = []
        for m in messages:
            if isinstance(m, HumanMessage):
                all_msgs_dict.append({"role": "user", "content": m.content})
            elif isinstance(m, AIMessage):
                all_msgs_dict.append(
                    {
                        "role": "assistant",
                        "content": m.content,
                        "tool_calls": m.additional_kwargs.get("tool_calls"),
                        "scratch_pad": m.additional_kwargs.get("scratch_pad"),
                    },
                )
            elif isinstance(m, ToolMessage):
                all_msgs_dict.append(
                    {
                        "role": "tool",
                        "content": m.content,
                        "tool_call_id": m.tool_call_id,
                        "name": m.name or "tool",
                    },
                )

        return all_msgs_dict

    @staticmethod
    async def _report_graph_progress(
        current_messages: Sequence[BaseMessage],
        last_msg_count: int,
        on_progress: Callable[..., Awaitable[None]],
    ) -> None:
        """Report intermediate assistant content and tool hints in their existing order."""
        if len(current_messages) > last_msg_count:
            new_msgs = current_messages[last_msg_count:]
            for m in new_msgs:
                if isinstance(m, AIMessage):
                    # Clean thinking blocks for progress reporting
                    content = str(m.content)
                    if "<think>" in content:
                        content = re.sub(
                            r"<think>.*?</think>", "", content, flags=re.DOTALL
                        ).strip()

                    # Only report content as progress if it's intermediate (has tool calls)
                    if content and hasattr(m, "tool_calls") and m.tool_calls:
                        await on_progress(content, tool_hint=False)

                    # Report tool hints in formatted style
                    if hasattr(m, "tool_calls") and m.tool_calls:
                        for tc in m.tool_calls:
                            args = tc.get("args", {})
                            if isinstance(args, dict) and len(args) == 1:
                                val = next(iter(args.values()))
                                hint = (
                                    f'{tc["name"]}("{val}")'
                                    if isinstance(val, str)
                                    else f"{tc['name']}({val})"
                                )
                            else:
                                try:
                                    hint = f"{tc['name']}({_json.dumps(args)})"
                                except Exception:
                                    hint = f"{tc['name']}({args})"
                            await on_progress(hint, tool_hint=True)
            last_msg_count = len(current_messages)

    @staticmethod
    def _graph_state_messages(state: object) -> list[BaseMessage]:
        """Validate the untyped LangGraph values-stream boundary before use."""
        if not isinstance(state, dict):
            raise TypeError("Graph values stream must yield a state mapping")
        messages = state.get("messages", [])
        if not isinstance(messages, Sequence):
            raise TypeError("Graph messages must be a sequence")
        result: list[BaseMessage] = []
        for message in messages:
            if not isinstance(message, BaseMessage):
                raise TypeError(
                    "Graph messages must contain LangChain BaseMessage values"
                )
            result.append(message)
        return result

    async def _run_agent_loop(
        self,
        initial_messages: list[dict[Any, Any]],
        on_progress: Callable[..., Awaitable[None]] | None = None,
        on_token: Callable[[str], Awaitable[None]] | None = None,
    ) -> tuple[str | None, list[str], list[dict[Any, Any]]]:
        """Run the agent iteration loop via LangGraph."""
        lc_msgs = self._to_graph_messages(initial_messages)

        # Execute graph with streaming for tokens
        tools_used: list[str] = []

        inputs: AgentState = {
            "messages": lc_msgs,
            "iterations": 0,
            "mode": self.mode,
            "plan": [],
            "current_task": None,
            "config": {
                "model": self.model,
                "llm_kwargs": {
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "reasoning_effort": self.reasoning_effort,
                    "fallback_models": self.fallback_models,
                    "on_token": on_token,  # Provider handles this
                },
            },
        }

        # Use invoke for now to keep it simple, while we verify plumbing
        # We can move to astream_events later for more granular control

        # Use astream to support progress callbacks for intermediate steps
        final_messages: list[BaseMessage] = lc_msgs
        last_msg_count = len(lc_msgs)

        from amberclaw.security import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
            NetworkPolicy,
            egress_sandbox,
        )

        policy_path = self.workspace / "egress_policy.yaml"
        policy = NetworkPolicy.load_from_yaml(policy_path)

        with egress_sandbox(policy):
            async for state in self._graph.runnable.astream(
                inputs, stream_mode="values"
            ):
                final_messages = self._graph_state_messages(state)
            if on_progress:
                await self._report_graph_progress(
                    final_messages, last_msg_count, on_progress
                )

        # Extract results
        last_msg = final_messages[-1]

        all_msgs_dict = self._from_graph_messages(final_messages)

        # Identify tools used from messages
        for m in final_messages:
            if isinstance(m, ToolMessage):
                tools_used.append("tool")

        return (
            str(last_msg.content) if isinstance(last_msg, AIMessage) else None,
            tools_used,
            all_msgs_dict,
        )

    async def run(self) -> None:
        """Run the agent loop, dispatching messages as tasks to stay responsive to /stop."""
        if self._plugin_stop_task is not None:
            await self._plugin_stop_task
            self._plugin_stop_task = None
        self._closing = False
        self._running = True
        await self._connect_mcp()

        # Start plugins and register their dynamic tools
        try:
            await self.plugin_manager.start()
            for tools in self.plugin_manager.proxy_tools.values():
                for tool in tools:
                    self.tools.register(tool)
        except Exception as e:
            logger.error("Failed to start plugins: {}", e)

        # Start background discovery
        if not self._mcp_discovery_task:
            self._mcp_discovery_task = asyncio.create_task(self._mcp_discovery_loop())

        logger.info("Agent loop started")

        while self._running:
            try:
                msg = await asyncio.wait_for(self.bus.consume_inbound(), timeout=1.0)
            except TimeoutError:
                continue

            if msg.metadata.get("system_event_type") == "low_memory":
                await self._handle_low_memory()
                continue

            if msg.content.strip().lower() == "/stop":
                await self._handle_stop(msg)
            elif msg.content.strip().lower().startswith("/pair"):
                self._track_dispatch(msg.session_key, self._handle_pairing(msg))
            else:
                self._track_dispatch(msg.session_key, self._dispatch(msg))

    async def _handle_low_memory(self) -> None:
        """Consolidate stored sessions when the runtime reports low memory."""
        logger.warning(
            "AgentLoop: System Low Memory alert received, initiating memory cleanup."
        )
        try:
            for s_info in self.sessions.list_sessions():
                s_key = s_info.get("key")
                if s_key:
                    session = self.sessions.get_or_create(s_key)
                    await self._consolidate_memory(session, archive_all=True)
            logger.info("AgentLoop: Memory consolidation complete.")
        except Exception as e:
            logger.error(
                "AgentLoop: Failed to consolidate memory on low memory event: {}",
                e,
            )

    def _track_work(
        self, key: str, coro: Coroutine[Any, Any, _WorkResult]
    ) -> asyncio.Task[_WorkResult]:
        """Own accepted work, including calls queued on the processing lock."""
        if self._closing:
            coro.close()
            raise RuntimeError("Agent loop is closing")
        task = asyncio.create_task(coro)
        self._active_tasks.setdefault(key, []).append(task)

        def discard(completed: asyncio.Task[_WorkResult]) -> None:
            tasks = self._active_tasks.get(key, [])
            if completed in tasks:
                tasks.remove(completed)
            if not tasks:
                self._active_tasks.pop(key, None)

        task.add_done_callback(discard)
        return task

    def _track_dispatch(self, key: str, coro: Coroutine[Any, Any, None]) -> None:
        self._track_work(key, coro)

    async def _handle_pairing(self, msg: InboundMessage) -> None:
        """Handle a /pair command message to authenticate a channel and user."""
        parts = msg.content.strip().split()
        if len(parts) < PAIR_COMMAND_PARTS:
            await self.bus.publish_outbound(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=(
                        "To pair this account/channel, run `/pair <code>` where <code> "
                        "is the 6-digit verification code generated by the administrator "
                        "on the system console."
                    ),
                )
            )
            return

        code = parts[1].strip()
        from amberclaw.security.dm_pairing import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
            verify_and_consume_code,
        )

        if verify_and_consume_code(code):
            paired = False
            if self.channels_config:
                ch_cfg = getattr(self.channels_config, msg.channel, None)
                if ch_cfg is not None and hasattr(ch_cfg, "allow_from"):
                    if msg.sender_id not in ch_cfg.allow_from:
                        ch_cfg.allow_from.append(msg.sender_id)
                        paired = True
                    else:
                        paired = True

            try:
                from amberclaw.config import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
                    loader,
                )

                config_path = loader.get_config_path()
                if config_path.exists():
                    cfg = loader.load_config(config_path)
                    target_cfg = getattr(cfg.channels, msg.channel, None)
                    if (
                        target_cfg is not None
                        and hasattr(target_cfg, "allow_from")
                        and msg.sender_id not in target_cfg.allow_from
                    ):
                        target_cfg.allow_from.append(msg.sender_id)
                        loader.save_config(cfg, config_path)
            except Exception as e:
                logger.error("Failed to persist paired channel configuration: {}", e)

            if paired:
                content = (
                    f"🎉 Access Granted! Your ID ({msg.sender_id}) has been successfully "
                    f"paired with the '{msg.channel}' channel."
                )
            else:
                content = (
                    f"⚠️ Pairing code was valid, but channel '{msg.channel}' could not "
                    f"be configured. Please contact the system administrator."
                )
        else:
            content = "❌ Invalid or expired pairing code. Please generate a new one."

        await self.bus.publish_outbound(
            OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=content,
            )
        )

    async def _handle_stop(self, msg: InboundMessage) -> None:
        """Cancel all active tasks and subagents for the session."""
        tasks = self._active_tasks.pop(msg.session_key, [])
        cancelled = sum(1 for t in tasks if not t.done() and t.cancel())
        for t in tasks:
            with suppress(asyncio.CancelledError, Exception):
                await t
        sub_cancelled = await self.subagents.cancel_by_session(msg.session_key)
        total = cancelled + sub_cancelled
        content = f"⏹ Stopped {total} task(s)." if total else "No active task to stop."
        await self.bus.publish_outbound(
            OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=content,
            ),
        )

    async def _dispatch(self, msg: InboundMessage) -> None:
        """Process a message under the global lock."""

        async def on_token(token: str) -> None:
            await self.bus.publish_outbound(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=token,
                    metadata={
                        "_token": True,
                        "message_id": msg.metadata.get("message_id"),
                    },
                ),
            )

        async with self._processing_lock:
            try:
                response = await self._process_message(msg, on_token=on_token)
                if response is not None:
                    await self.bus.publish_outbound(response)
                elif msg.channel == "cli":
                    await self.bus.publish_outbound(
                        OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content="",
                            metadata=msg.metadata or {},
                        ),
                    )
            except asyncio.CancelledError:
                logger.info("Task cancelled for session {}", msg.session_key)
                raise
            except Exception:
                logger.exception(
                    "Error processing message for session {}", msg.session_key
                )
                await self.bus.publish_outbound(
                    OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content="Sorry, I encountered an error.",
                    ),
                )

    def _owns_work(self, task: asyncio.Task[Any] | None) -> bool:
        if task is None:
            return False
        return (
            any(task in tasks for tasks in self._active_tasks.values())
            or task in self._consolidation_tasks
            or self.subagents.owns_task(task)
        )

    async def _drain_work(self) -> None:
        current = asyncio.current_task()
        tasks = {task for group in self._active_tasks.values() for task in group}
        tasks.update(self._consolidation_tasks)
        if current is not None:
            tasks.discard(current)
        for task in tasks:
            task.cancel()
        try:
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            self._active_tasks.clear()
            self._consolidation_tasks.clear()
            await self.subagents.cancel_all()

    async def _close_mcp_transports(self) -> None:
        try:
            discovery = self._mcp_discovery_task
            try:
                if discovery is not None:
                    discovery.cancel()
                    with suppress(asyncio.CancelledError):
                        await discovery
            finally:
                if self._mcp_stack:
                    with suppress(RuntimeError, BaseExceptionGroup):
                        await self._mcp_stack.aclose()
        finally:
            self._mcp_stack = None
            self._mcp_connected = False
            self._mcp_discovery_task = None

    async def _shutdown_runtime(self) -> None:
        """Drain work before tool transports; attempt all cleanup after failures."""
        try:
            try:
                await self._drain_work()
            finally:
                await self.plugin_manager.stop()
        finally:
            await self._close_mcp_transports()

    async def close_mcp(self) -> None:
        """Await shutdown outside owned work; owned callers defer to its worker.

        Awaiting the worker from a task it is draining would await itself. Such
        a caller requests shutdown and returns; an external owner can await the
        retained worker to establish completed cleanup.
        """
        self.stop()
        task = self._plugin_stop_task
        if task is None or self._owns_work(asyncio.current_task()):
            return
        try:
            await task
        finally:
            if self._plugin_stop_task is task:
                self._plugin_stop_task = None

    def stop(self) -> None:
        """Stop accepting work and retain its cleanup worker until observed."""
        self._running = False
        self._closing = True
        logger.info("Agent loop stopping")
        if self._plugin_stop_task is None:
            self._plugin_stop_task = asyncio.create_task(self._shutdown_runtime())

    async def _process_system_message(
        self, msg: InboundMessage, on_token: Callable[[str], Awaitable[None]] | None
    ) -> OutboundMessage:
        """Route a background result to its originating conversation."""
        channel, chat_id = (
            msg.chat_id.split(":", 1) if ":" in msg.chat_id else ("cli", msg.chat_id)
        )
        logger.info("Processing system message from {}", msg.sender_id)
        key = f"{channel}:{chat_id}"
        session = self.sessions.get_or_create(key)
        self._set_tool_context(channel, chat_id, msg.metadata.get("message_id"))
        history = session.get_history(max_messages=self.memory_window)
        messages = self.context.build_messages(
            history=history,
            current_message=msg.content,
            channel=channel,
            chat_id=chat_id,
        )
        from amberclaw.security.auth import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
            active_sender_context,
        )

        with active_sender_context(msg.sender_id):
            final_content, _, all_msgs = await self._run_agent_loop(
                messages,
                on_token=on_token,
            )
        self._save_turn(session, all_msgs, 1 + len(history))
        self.sessions.save(session)
        return OutboundMessage(
            channel=channel,
            chat_id=chat_id,
            content=final_content or "Background task completed.",
        )

    async def _start_new_session(
        self, msg: InboundMessage, session: Session
    ) -> OutboundMessage:
        """Archive the existing messages before clearing a conversation."""
        lock = self._consolidation_locks.setdefault(session.key, asyncio.Lock())
        self._consolidating.add(session.key)
        try:
            async with lock:
                snapshot = session.messages[session.last_consolidated :]
                if snapshot:
                    temp = Session(key=session.key)
                    temp.messages = list(snapshot)
                    if not await self._consolidate_memory(temp, archive_all=True):
                        return OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content="Memory archival failed, session not cleared. Please try again.",
                        )
        except Exception:
            logger.exception("/new archival failed for {}", session.key)
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="Memory archival failed, session not cleared. Please try again.",
            )
        finally:
            self._consolidating.discard(session.key)

        session.clear()
        self.sessions.save(session)
        self.sessions.invalidate(session.key)
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content="New session started.",
        )

    def _schedule_consolidation(self, session: Session) -> None:
        """Own background archival tasks and their per-session locks."""
        unconsolidated = len(session.messages) - session.last_consolidated
        if (
            unconsolidated >= self.memory_window
            and session.key not in self._consolidating
        ):
            self._consolidating.add(session.key)
            lock = self._consolidation_locks.setdefault(session.key, asyncio.Lock())

            async def _consolidate_and_unlock() -> None:
                try:
                    async with lock:
                        await self._consolidate_memory(session)
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(
                        "Background memory consolidation failed for session {}: {}",
                        session.key,
                        e,
                    )
                finally:
                    self._consolidating.discard(session.key)
                    _task = asyncio.current_task()
                    if _task is not None:
                        self._consolidation_tasks.discard(_task)

            _task = asyncio.create_task(_consolidate_and_unlock())
            self._consolidation_tasks.add(_task)

    async def _prepare_context_budget(
        self,
        msg: InboundMessage,
        session: Session,
        history: list[dict[str, Any]],
        initial_messages: list[dict[str, Any]],
    ) -> str | None:
        """Apply existing memory nudges and return the context budget warning."""
        # Trigger Proactive MemoryNudgeSystem (AC-061)
        try:
            from amberclaw.agent.learning.nudge_system import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
                MemoryNudgeSystem,
            )

            nudge_sys = MemoryNudgeSystem(self.workspace)
            if nudge_msg := nudge_sys.should_nudge(history, msg.content):
                initial_messages.append({"role": "system", "content": nudge_msg})
        except Exception as e:
            logger.error("Failed to run MemoryNudgeSystem: {}", e)

        # Token and Context Budget System (AC-059)
        approx_tokens = count_tokens(
            initial_messages, model=getattr(self, "model", "gpt-4o")
        )
        limit = self.max_tokens or 128000

        warning_msg = None
        if approx_tokens > limit * 0.95:
            # Trigger summary consolidation
            await self._consolidate_memory(session, archive_all=False)
            warning_msg = (
                "Context window near 95% limit. Triggered automatic summarization."
            )
        elif approx_tokens > limit * 0.80:
            warning_msg = f"Context window at {int((approx_tokens / limit) * 100)}% capacity. Consider /new soon."

        return warning_msg

    @staticmethod
    def _message_preview(content: str, max_chars: int) -> str:
        """Bound log message text to the existing preview limit."""
        return content[:max_chars] + "..." if len(content) > max_chars else content

    async def _process_message(
        self,
        msg: InboundMessage,
        session_key: str | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
        on_token: Callable[[str], Awaitable[None]] | None = None,
    ) -> OutboundMessage | None:
        """Process a single inbound message and return the response."""
        from amberclaw.config.schema import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
            settings,
        )

        if settings.security.pii_redaction:
            msg.content = self.pii_redactor.redact(msg.content)
        # System messages: parse origin from chat_id ("channel:chat_id")
        if msg.channel == "system":
            return await self._process_system_message(msg, on_token)

        preview = self._message_preview(msg.content, INBOUND_LOG_PREVIEW_CHARS)
        logger.info(
            "Processing message from {}:{}: {}", msg.channel, msg.sender_id, preview
        )

        key = session_key or msg.session_key
        session = self.sessions.get_or_create(key)

        # Slash commands
        cmd = msg.content.strip().lower()
        if cmd == "/new":
            return await self._start_new_session(msg, session)
        if cmd == "/help":
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="🐈 amberclaw commands:\n/new — Start a new conversation\n/stop — Stop the current task\n/feedback <msg> — Provide self-improvement feedback\n/help — Show available commands",
            )
        if cmd.startswith("/feedback "):
            feedback = msg.content[len("/feedback ") :].strip()
            MemoryStore(self.workspace).append_feedback(feedback)
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="Feedback stored for future self-improvement.",
            )

        self._schedule_consolidation(session)

        self._set_tool_context(msg.channel, msg.chat_id, msg.metadata.get("message_id"))
        if isinstance(message_tool := self.tools.get("message"), MessageTool):
            message_tool.start_turn()

        history = session.get_history(max_messages=self.memory_window)
        initial_messages = self.context.build_messages(
            history=history,
            current_message=msg.content,
            media=msg.media if msg.media else None,
            channel=msg.channel,
            chat_id=msg.chat_id,
        )

        warning_msg = await self._prepare_context_budget(
            msg, session, history, initial_messages
        )

        async def _bus_progress(content: str, *, tool_hint: bool = False) -> None:
            meta = dict(msg.metadata or {})
            meta["_progress"] = True
            meta["_tool_hint"] = tool_hint
            if settings.security.pii_redaction:
                content = self.pii_redactor.redact(content)
            await self.bus.publish_outbound(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=content,
                    metadata=meta,
                ),
            )

        from amberclaw.security.auth import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
            active_sender_context,
        )

        with active_sender_context(msg.sender_id):
            final_content, _, all_msgs = await self._run_agent_loop(
                initial_messages,
                on_progress=on_progress or _bus_progress,
                on_token=on_token,
            )

        if final_content is None:
            final_content = "I've completed processing but have no response to give."

        if warning_msg:
            final_content += f"\n\n[System] {warning_msg}"

        if settings.security.pii_redaction:
            final_content = self.pii_redactor.redact(final_content)

        self._save_turn(session, all_msgs, 1 + len(history))
        self.sessions.save(session)

        # Trigger Autonomous SkillCreator (AC-060)
        try:
            from amberclaw.agent.learning.skill_creator import (  # noqa: PLC0415 - load the optional runtime dependency only for this operation
                SkillCreator,
            )

            skill_creator = SkillCreator(self.provider, self.workspace)
            await skill_creator.monitor_and_create(all_msgs, model=self.model)
        except Exception as e:
            logger.error("Failed to run SkillCreator: {}", e)

        if (
            (mt := self.tools.get("message"))
            and isinstance(mt, MessageTool)
            and mt._sent_in_turn
        ):
            return None

        preview = self._message_preview(final_content, OUTBOUND_LOG_PREVIEW_CHARS)
        logger.info("Response to {}:{}: {}", msg.channel, msg.sender_id, preview)
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content,
            metadata=msg.metadata or {},
        )

    @staticmethod
    def _persistable_user_parts(content: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Drop runtime metadata and replace inline image payloads for persistence."""
        filtered = []
        for c in content:
            if (
                c.get("type") == "text"
                and isinstance(c.get("text"), str)
                and c["text"].startswith(ContextBuilder._RUNTIME_CONTEXT_TAG)
            ):
                continue  # Strip runtime context from multimodal messages
            if c.get("type") == "image_url" and c.get("image_url", {}).get(
                "url",
                "",
            ).startswith("data:image/"):
                filtered.append({"type": "text", "text": "[image]"})
            else:
                filtered.append(c)
        return filtered

    def _save_turn(
        self, session: Session, messages: list[dict[Any, Any]], skip: int
    ) -> None:
        """Save new-turn messages into session, truncating large tool results."""

        for m in messages[skip:]:
            entry = dict(m)
            role, content = entry.get("role"), entry.get("content")
            if role == "assistant" and not content and not entry.get("tool_calls"):
                continue  # skip empty assistant messages — they poison session context
            if (
                role == "tool"
                and isinstance(content, str)
                and len(content) > self._TOOL_RESULT_MAX_CHARS
            ):
                entry["content"] = (
                    content[: self._TOOL_RESULT_MAX_CHARS] + "\n... (truncated)"
                )
            elif role == "user":
                if isinstance(content, str) and content.startswith(
                    ContextBuilder._RUNTIME_CONTEXT_TAG,
                ):
                    # Strip the runtime-context prefix, keep only the user text.
                    parts = content.split("\n\n", 1)
                    if len(parts) > 1 and parts[1].strip():
                        entry["content"] = parts[1]
                    else:
                        continue
                if isinstance(content, list):
                    filtered = self._persistable_user_parts(content)
                    if not filtered:
                        continue
                    entry["content"] = filtered
            entry.setdefault(
                "timestamp",
                datetime.now().astimezone().replace(tzinfo=None).isoformat(),
            )
            session.messages.append(entry)
        session.updated_at = datetime.now().astimezone().replace(tzinfo=None)

    async def _consolidate_memory(
        self, session: Session, archive_all: bool = False
    ) -> bool:
        """Delegate to MemoryStore.consolidate(). Returns True on success."""
        return await MemoryStore(self.workspace).consolidate(
            session,
            self.provider,
            self.model,
            archive_all=archive_all,
            memory_window=self.memory_window,
        )

    async def process_direct(  # noqa: PLR0913 - preserve public direct-processing callback and routing arguments
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        on_progress: Callable[[str], Awaitable[None]] | None = None,
        on_token: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        """Process an owned message with the same serialization as bus dispatch."""
        message = InboundMessage(
            channel=channel, sender_id="user", chat_id=chat_id, content=content
        )
        task = self._track_work(
            session_key, self._run_direct(message, session_key, on_progress, on_token)
        )
        return await task

    async def _run_direct(
        self,
        message: InboundMessage,
        session_key: str,
        on_progress: Callable[[str], Awaitable[None]] | None,
        on_token: Callable[[str], Awaitable[None]] | None,
    ) -> str:
        await self._connect_mcp()
        async with self._processing_lock:
            response = await self._process_message(
                message,
                session_key=session_key,
                on_progress=on_progress,
                on_token=on_token,
            )
        return response.content if response else ""
