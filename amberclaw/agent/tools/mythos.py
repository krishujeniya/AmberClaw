"""AmberClaw Mythos — recursive multi-depth reasoning tool.

Forces the agent to think at multiple abstraction levels before answering.
Uses the agent's own provider/model. No external deps.
"""

from __future__ import annotations

import re
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.agent.tools.base import PydanticTool


class MythosArgs(BaseModel):
    """Arguments for the mythos_think tool."""

    query: str = Field(..., description="The question or problem to reason through deeply.")
    depth: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Reasoning depth (1=quick, 3=default thorough, 5=maximum).",
    )


class MythosTool(PydanticTool):
    """Deep recursive reasoning tool — forces multi-layer analysis before finalizing answer."""

    name = "mythos_think"
    description = (
        "Perform deep, multi-layer reasoning on a complex question. "
        "Each depth level re-examines the problem for hidden assumptions, edge cases, "
        "and deeper insights. Returns a synthesized final answer from all reasoning layers. "
        "Use for hard problems, critical decisions, or when the first answer feels incomplete."
    )
    args_schema = MythosArgs

    def __init__(self, provider: Any, model: str, temperature: float = 0.1, max_tokens: int = 2048):
        super().__init__()
        self._provider = provider
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    async def _ask(self, prompt: str) -> str:
        try:
            resp = await self._provider.chat_with_retry(
                messages=[{"role": "user", "content": prompt}],
                tools=[],
                model=self._model,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
            return (resp.content or "").strip()
        except Exception as exc:
            logger.warning("Mythos: LLM call failed: {}", exc)
            return ""

    @staticmethod
    def _extract_thought(text: str) -> str:
        """Pull content from <thought>…</thought> or return full text."""
        m = re.search(r"<thought>(.*?)</thought>", text, re.DOTALL)
        return m.group(1).strip() if m else text.strip()

    async def run(self, args: MythosArgs) -> str:
        context = f"Initial Query: {args.query}\n"
        logger.info("Mythos: depth={} on query: {}", args.depth, args.query[:80])

        for i in range(1, args.depth + 1):
            prompt = (
                f"{context}\n"
                f"You are at reasoning depth {i} of {args.depth}. "
                "Analyze the problem more deeply. Look for hidden assumptions, "
                "second-order effects, and edge cases missed in previous layers. "
                "Wrap your reasoning in <thought> tags."
            )
            raw = await self._ask(prompt)
            thought = self._extract_thought(raw)
            context += f"\nReasoning Depth {i}:\n{thought}\n"
            logger.debug("Mythos depth {}: {} chars", i, len(thought))

        synthesis_prompt = (
            f"{context}\n"
            "Based on all reasoning layers above, provide the final, definitive answer. "
            "Be concise, accurate, and incorporate the best insights from each depth. "
            "Do not repeat the reasoning layers — only the conclusion."
        )
        final = await self._ask(synthesis_prompt)

        meta = f"\n\n---\n*Mythos reasoning: {args.depth} depth level(s)*"
        return (final or "Mythos produced no final answer.") + meta
