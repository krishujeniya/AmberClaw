"""AmberClaw Personal Assistant tool.

Self-contained conversational memory assistant.
Uses the agent's configured provider — no external personal/* module required.
Stores conversation history in the workspace SQLite-style JSON store.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.agent.tools.base import PydanticTool


class AssistantArgs(BaseModel):
    """Arguments for the personal_assistant tool."""

    message: str = Field(..., description="Your question, instruction, or note to the assistant.")
    session_id: str = Field(
        default="default",
        description="Session thread ID — use distinct IDs for separate conversation topics.",
    )


class AssistantTool(PydanticTool):
    """Personal conversational assistant with persistent local memory per session."""

    name = "personal_assistant"
    description = (
        "Talk to your personal AI assistant. Maintains conversation history per session. "
        "Useful for: drafting content, answering personal questions, brainstorming, "
        "or any task requiring back-and-forth context within a session."
    )
    args_schema = AssistantArgs

    _HISTORY_VERSION = 1

    def __init__(
        self,
        provider: Any,
        model: str,
        workspace: Path,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_prompt: str = "",
    ):
        super().__init__()
        self._provider = provider
        self._model = model
        self._workspace = workspace
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._system_prompt = system_prompt or (
            "You are a helpful personal assistant integrated into AmberClaw. "
            "Be concise, accurate, and remember context within this session."
        )
        self._store_dir = workspace / "personal_assistant"
        self._store_dir.mkdir(parents=True, exist_ok=True)

    def _history_path(self, session_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
        return self._store_dir / f"{safe}.json"

    def _load_history(self, session_id: str) -> list[dict]:
        p = self._history_path(session_id)
        if not p.exists():
            return []
        try:
            data = json.loads(p.read_text())
            return data.get("messages", [])
        except Exception:
            return []

    def _save_history(self, session_id: str, messages: list[dict]) -> None:
        p = self._history_path(session_id)
        try:
            p.write_text(json.dumps({
                "version": self._HISTORY_VERSION,
                "session_id": session_id,
                "updated_at": time.time(),
                "messages": messages[-40:],  # cap at 40 turns per session
            }, indent=2))
        except Exception as exc:
            logger.warning("PersonalAssistant: failed to save history: {}", exc)

    async def run(self, args: AssistantArgs) -> str:
        history = self._load_history(args.session_id)
        history.append({"role": "user", "content": args.message})

        messages = [
            {"role": "system", "content": self._system_prompt},
            *history,
        ]

        try:
            resp = await self._provider.chat_with_retry(
                messages=messages,
                tools=[],
                model=self._model,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
            reply = (resp.content or "").strip()
        except Exception as exc:
            logger.error("PersonalAssistant: LLM error: {}", exc)
            return f"Assistant error: {exc}"

        history.append({"role": "assistant", "content": reply})
        self._save_history(args.session_id, history)
        return reply
