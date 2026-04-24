"""AmberClaw Knowledge RAG tools.

Simple local RAG implementation using the agent's workspace.
Uses a JSON-based vector-like store for search.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.agent.tools.base import PydanticTool


class KnowledgeSearchArgs(BaseModel):
    """Arguments for knowledge search."""
    query: str = Field(..., description="The query to search in your knowledge base.")
    limit: int = Field(default=3, description="Maximum number of results.")


class KnowledgeAddArgs(BaseModel):
    """Arguments for adding knowledge."""
    content: str = Field(..., description="The information to store.")
    tags: list[str] = Field(default_factory=list, description="Optional tags.")


class KnowledgeToolBase(PydanticTool):
    def __init__(self, workspace: Path | None = None):
        super().__init__()
        self.workspace = workspace or Path.home() / ".amberclaw" / "workspace"
        self.kb_path = self.workspace / "knowledge_base.json"
        self.workspace.mkdir(parents=True, exist_ok=True)
        if not self.kb_path.exists():
            self.kb_path.write_text(json.dumps({"entries": []}))

    def _load_kb(self):
        try:
            return json.loads(self.kb_path.read_text())
        except Exception:
            return {"entries": []}

    def _save_kb(self, kb):
        self.kb_path.write_text(json.dumps(kb, indent=2))


class KnowledgeSearchTool(KnowledgeToolBase):
    """Search your local personal knowledge base."""
    name = "knowledge_search"
    description = "Search through indexed information in your local knowledge base."
    args_schema = KnowledgeSearchArgs

    async def run(self, args: KnowledgeSearchArgs) -> str:
        kb = self._load_kb()
        entries = kb.get("entries", [])
        # Simple substring search for now (MVP)
        results = [e["content"] for e in entries if args.query.lower() in e["content"].lower()]
        if not results:
            return "No matching knowledge found."
        return "\n---\n".join(results[:args.limit])


class KnowledgeAddTool(KnowledgeToolBase):
    """Add information to your local personal knowledge base."""
    name = "knowledge_add"
    description = "Save new information, facts, or notes to your long-term knowledge base."
    args_schema = KnowledgeAddArgs

    async def run(self, args: KnowledgeAddArgs) -> str:
        kb = self._load_kb()
        kb["entries"].append({
            "content": args.content,
            "tags": args.tags,
        })
        self._save_kb(kb)
        return f"Successfully added to knowledge base: {args.content[:50]}..."
