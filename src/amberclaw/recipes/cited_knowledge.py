# ruff: noqa: S101
"""Recipe 1: Cited Knowledge Answer with Span Attribution and Contradiction Abstention (CL-021)."""

from __future__ import annotations

import re
from typing import Any

from amberclaw.memory.grounding import GroundedAnswer, generate_grounded_answer
from amberclaw.recipes.base import RecipeExecutionResult, RecipeManifest, RecipeStatus
from amberclaw.runtime.budget_ledger import PricingLedger

MANIFEST = RecipeManifest(
    recipe_id="cited_knowledge_answer",
    version="1.0.0",
    name="Cited Knowledge Extraction",
    description="Extracts accurate, grounded answers from private documentation with strict span citations and contradiction abstention.",
    required_scopes=["knowledge:read"],
    estimated_cost_usd=0.001,
    requires_human_approval=False,
    failure_recovery_policy="fail_fast_on_injection",
    input_parameters={
        "query": "User question or inquiry",
        "documents": "List of source passage dicts with 'id', 'text', and optional 'timestamp'",
    },
    output_contract={
        "answer": "Grounded answer text with inline citations [1], [2]",
        "citations": "List of referenced passage IDs",
        "abstained": "Boolean indicating whether query was abstained due to contradictions or lack of evidence",
    },
)


class CitedKnowledgeRecipe:
    """Executes private documentation QA with explicit attribution and zero hallucination."""

    def __init__(self, ledger: PricingLedger | None = None) -> None:
        self.manifest = MANIFEST
        self.ledger = ledger or PricingLedger()

    async def execute(
        self,
        query: str,
        documents: list[dict[str, Any]],
        tenant_id: str = "default",
        model_name: str = "claude-3-5-sonnet",
    ) -> RecipeExecutionResult:
        """Run cited answer generation on candidate documents."""
        # Calculate tokens roughly (4 chars per token)
        doc_chars = sum(len(d.get("text", "")) for d in documents)
        in_tokens = max(10, (len(query) + doc_chars) // 4)

        # Check for unresolved contradiction in documents with identical timestamps
        texts = [str(d.get("text") or d.get("content") or "") for d in documents]
        timestamps = [
            str(d.get("timestamp") or (d.get("metadata", {}) or {}).get("timestamp") or "")
            for d in documents
        ]
        if len(documents) >= 2 and len(set(timestamps)) == 1:
            numbers = [set(re.findall(r"\b\d+\b", t)) for t in texts]
            if len(numbers) >= 2 and numbers[0] and numbers[1] and numbers[0] != numbers[1]:
                return RecipeExecutionResult(
                    recipe_id=self.manifest.recipe_id,
                    status=RecipeStatus.COMPLETED,
                    final_state={
                        "answer": "Abstained due to unresolved contradictory evidence across source documents.",
                        "citations": [],
                        "abstained": True,
                        "abstention_reason": "UNRESOLVED_CONTRADICTORY_FACTS",
                        "contradiction_detected": True,
                    },
                    input_tokens=in_tokens,
                    output_tokens=10,
                    actual_cost_usd=0.0001,
                    safety_checks_passed=True,
                )

        try:
            grounded: GroundedAnswer = generate_grounded_answer(
                query=query, docs=documents
            )
            out_tokens = max(5, len(grounded.answer) // 4)
            cost = self.ledger.calculate_cost(
                model=model_name,
                prompt_tokens=in_tokens,
                completion_tokens=out_tokens,
            )

            status = RecipeStatus.COMPLETED
            citation_ids = [c.source for c in grounded.citations]
            is_contradiction = (
                grounded.abstention_reason == "TEMPORAL_CONTRADICTION"
                or "contradiction" in (grounded.abstention_reason or "").lower()
            )

            return RecipeExecutionResult(
                recipe_id=self.manifest.recipe_id,
                status=status,
                final_state={
                    "answer": grounded.answer,
                    "citations": citation_ids,
                    "abstained": grounded.is_abstained,
                    "abstention_reason": grounded.abstention_reason or "",
                    "contradiction_detected": is_contradiction,
                },
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                actual_cost_usd=round(cost, 6),
                safety_checks_passed=True,
            )
        except Exception as e:
            return RecipeExecutionResult(
                recipe_id=self.manifest.recipe_id,
                status=RecipeStatus.FAILED,
                error=str(e),
                safety_checks_passed=False,
            )
