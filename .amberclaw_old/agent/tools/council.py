"""AmberClaw Council — multi-model consensus tool.

Runs a 3-stage council: collect → peer-rank → synthesize.
Uses the agent's own LLM provider + config. Zero external deps.
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from amberclaw.agent.tools.base import PydanticTool


class CouncilArgs(BaseModel):
    """Arguments for the council_consensus tool."""

    query: str = Field(..., description="The question or task to put to the council.")
    models: list[str] = Field(
        default_factory=list,
        description=(
            "List of model IDs to consult (e.g. ['openai/gpt-4o', 'anthropic/claude-opus-4-5']). "
            "Leave empty to use the two cheapest available models from config."
        ),
    )
    depth: int = Field(
        default=1,
        ge=1,
        le=3,
        description="Number of peer-ranking rounds (1=fast, 3=thorough).",
    )


class CouncilTool(PydanticTool):
    """Multi-model consensus tool — ask multiple LLMs, rank answers, synthesize best response."""

    @property
    def name(self) -> str:
        return "council_consensus"

    @property
    def description(self) -> str:
        return (
            "Run a multi-model council to get a high-confidence answer. "
            "Stage 1: each model answers independently. "
            "Stage 2: models anonymously rank each other's answers. "
            "Stage 3: the primary model synthesizes the final response. "
            "Use for complex, high-stakes questions where one model's blind spot could be costly."
        )

    @property
    def args_schema(self) -> type[CouncilArgs]:
        return CouncilArgs

    def __init__(self, provider: Any, model: str, temperature: float = 0.1, max_tokens: int = 2048):
        super().__init__()
        self._provider = provider
        self._primary_model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    async def _ask(self, model: str, messages: list[dict], on_token: Any | None = None) -> str:
        """Query a single model, return text or empty string on error."""
        try:
            resp = await self._provider.chat_with_retry(
                messages=messages,
                tools=[],
                model=model,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                on_token=on_token,
            )
            return (resp.content or "").strip()
        except Exception as exc:
            logger.warning("Council: model {} failed: {}", model, exc)
            return ""

    async def run(self, args: CouncilArgs, on_token: Any | None = None) -> str:
        models = args.models or [self._primary_model]
        if len(models) == 1:
            models = models * 2  # degenerate case: same model twice, still useful for ranking

        logger.info("Council: stage 1 — {} models on query: {}", len(models), args.query[:80])

        # ── Stage 1: Collect ──────────────────────────────────────────────────
        user_msg = [{"role": "user", "content": args.query}]
        tasks = [self._ask(m, user_msg) for m in models]
        raw_responses = await asyncio.gather(*tasks)

        stage1: list[dict] = [
            {"model": m, "response": r} for m, r in zip(models, raw_responses) if r
        ]
        if not stage1:
            return "Council failed: all models returned empty responses."

        # ── Stage 2: Peer Ranking ─────────────────────────────────────────────
        labels = [chr(65 + i) for i in range(len(stage1))]
        responses_block = "\n\n".join(
            f"Response {lbl}:\n{item['response']}" for lbl, item in zip(labels, stage1)
        )
        ranking_prompt = (
            f"You are an anonymous peer reviewer.\n\n"
            f"Original question: {args.query}\n\n"
            f"{responses_block}\n\n"
            "Rank these responses from best to worst. "
            "Give a 1-sentence reason for each rank. "
            "Format: RANK 1: Response X — reason."
        )
        rank_msgs = [{"role": "user", "content": ranking_prompt}]

        for _round in range(args.depth):
            rank_tasks = [self._ask(m, rank_msgs) for m in models]
            rankings = await asyncio.gather(*rank_tasks)
            stage1_rankings = [r for r in rankings if r]

        # ── Stage 3: Synthesis ────────────────────────────────────────────────
        stage1_block = "\n\n".join(f"[{item['model']}]: {item['response']}" for item in stage1)
        rankings_block = "\n\n".join(stage1_rankings) if stage1_rankings else "(no rankings)"
        synthesis_prompt = (
            f"You are synthesizing a council of AI experts.\n\n"
            f"Original question: {args.query}\n\n"
            f"Individual responses:\n{stage1_block}\n\n"
            f"Peer rankings:\n{rankings_block}\n\n"
            "Synthesize the single best answer, incorporating the strongest points "
            "and discarding weak or contradictory ones. Be direct and complete."
        )
        final = await self._ask(
            self._primary_model,
            [{"role": "user", "content": synthesis_prompt}],
            on_token=on_token,
        )

        meta = f"\n\n---\n*Council used {len(stage1)} models · {args.depth} ranking round(s)*"
        return (final or "Synthesis produced no output.") + meta
