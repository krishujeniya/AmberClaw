"""AmberClaw Personal Assistant tool.

Self-contained conversational memory assistant.
Integrated with Mem0 for long-term fact extraction and session management.
"""

from __future__ import annotations

import json
import time
import os
from pathlib import Path
from typing import Any, Optional
from cryptography.fernet import Fernet

from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.agent.tools.base import PydanticTool


class AssistantArgs(BaseModel):
    """Arguments for the personal_assistant tool."""

    message: str = Field(..., description="Your question, instruction, or note to the assistant.")
    session_id: str = Field(
        default="default",
        description="Session thread ID — used for session-specific conversational context.",
    )


class AssistantTool(PydanticTool):
    """Personal conversational assistant with persistent long-term memory and session context via Mem0."""

    @property
    def name(self) -> str:
        return "personal_assistant"

    @property
    def description(self) -> str:
        return (
            "Talk to your personal AI assistant. Remembers facts across sessions and "
            "maintains conversational context. Automatically extracts and recalls personal preferences."
        )

    @property
    def args_schema(self) -> type[AssistantArgs]:
        return AssistantArgs

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
            "Be concise, accurate, and use your long-term memory to provide personalized responses."
        )

        # Initialize Mem0
        try:
            from mem0 import Memory

            # Local configuration for Mem0
            config = {
                "vector_store": {
                    "provider": "chroma",
                    "config": {
                        "path": str(workspace / "mem0_db"),
                    },
                }
            }
            self._memory = Memory.from_config(config)
            logger.info("PersonalAssistant: initialized with Mem0 long-term memory.")
        except Exception as e:
            logger.warning(
                "PersonalAssistant: failed to initialize Mem0: {}. Falling back to basic history.",
                e,
            )
            self._memory = None

        # Basic session history (JSON fallback/short-term)
        self._store_dir = workspace / "personal_assistant"
        self._store_dir.mkdir(parents=True, exist_ok=True)

    def _history_path(self, session_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
        ext = ".json.enc" if os.environ.get("AMBERCLAW_HISTORY_KEY") else ".json"
        return self._store_dir / f"{safe}{ext}"

    def _get_fernet(self) -> Optional[Fernet]:
        key = os.environ.get("AMBERCLAW_HISTORY_KEY")
        if not key:
            return None
        try:
            return Fernet(key.encode())
        except Exception as e:
            logger.error("PersonalAssistant: invalid encryption key: {}", e)
            return None

    def _load_session_history(self, session_id: str) -> list[dict]:
        p = self._history_path(session_id)
        if not p.exists():
            return []
        try:
            raw = p.read_bytes()
            fernet = self._get_fernet()
            if fernet:
                raw = fernet.decrypt(raw)
            data = json.loads(raw)
            return data.get("messages", [])
        except Exception as e:
            logger.debug("PersonalAssistant: failed to load history (check key?): {}", e)
            return []

    def _save_session_history(self, session_id: str, messages: list[dict]) -> None:
        p = self._history_path(session_id)
        try:
            data = json.dumps(
                {
                    "session_id": session_id,
                    "updated_at": time.time(),
                    "messages": messages[-20:],  # keep last 20 messages for context
                },
                indent=2,
            ).encode()

            fernet = self._get_fernet()
            if fernet:
                data = fernet.encrypt(data)

            p.write_bytes(data)
        except Exception as exc:
            logger.warning("PersonalAssistant: failed to save session history: {}", exc)

    async def run(self, args: AssistantArgs) -> str:
        # 1. Load session context (short-term)
        session_history = self._load_session_history(args.session_id)

        # 2. Retrieve long-term memories (facts)
        memories_text = ""
        if self._memory:
            try:
                # Search across all memories for relevant facts
                # We use session_id as user_id for isolation, or swap for global user_id
                memories = self._memory.search(args.message, user_id=args.session_id)
                if memories:
                    facts = []
                    for m in memories:
                        # Mem0 search can return dicts or objects depending on the version/provider
                        val = None
                        if isinstance(m, dict):
                            val = m.get("memory")
                        elif hasattr(m, "memory"):
                            val = getattr(m, "memory")

                        if val:
                            facts.append(str(val))
                    if facts:
                        memories_text = "\n[RECALLED FACTS]:\n- " + "\n- ".join(facts)
            except Exception as e:
                logger.debug("Mem0 search failed: {}", e)

        # 3. Construct prompt
        system_content = f"{self._system_prompt}\n{memories_text}"

        history = [{"role": "user", "content": args.message}]
        full_history = session_history + history

        messages = [
            {"role": "system", "content": system_content},
            *full_history,
        ]

        # 4. LLM Call
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

        # 5. Store new information
        if self._memory:
            try:
                # Add to Mem0 (it auto-extracts facts from the user message)
                # We do this asynchronously to not block
                self._memory.add(args.message, user_id=args.session_id)
            except Exception as e:
                logger.debug("Mem0 add failed: {}", e)

        # 6. Update session history
        full_history.append({"role": "assistant", "content": reply})
        self._save_session_history(args.session_id, full_history)

        return reply
