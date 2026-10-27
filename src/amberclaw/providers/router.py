"""Intelligent cost-aware and latency-aware LLM router."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from amberclaw.providers.capabilities import ProviderCapability, detect_capabilities
from amberclaw.providers.resilience import CircuitState, get_circuit_breaker


class RoutingStrategy(StrEnum):
    """Routing strategies for candidate model selection."""

    COST_OPTIMIZED = "cost_optimized"  # Lowest token cost matching requirements
    LATENCY_OPTIMIZED = "latency_optimized"  # Lowest p50/p95 latency and highest health
    BALANCED = "balanced"  # Balance health score, latency, and cost
    QUALITY_OPTIMIZED = "quality_optimized"  # Highest capability and reasoning depth


class RoutingRequirement(BaseModel):
    """Capability requirements for filtering candidate models."""

    tools_required: bool = False
    json_required: bool = False
    vision_required: bool = False
    audio_required: bool = False
    min_context_window: int = 4096
    reasoning_required: bool = False
    max_cost_per_token: float | None = None


class RoutingDecision(BaseModel):
    """Result of model routing evaluation."""

    selected_model: str
    strategy: RoutingStrategy
    score: float
    reason: str
    evaluated_candidates: list[dict[str, Any]] = Field(default_factory=list)


class ModelRouter:
    """Evaluates candidate models and selects the optimal model given strategy and requirements."""

    def __init__(self, default_strategy: RoutingStrategy = RoutingStrategy.BALANCED):
        self.default_strategy = default_strategy

    def satisfies_requirements(
        self,
        cap: ProviderCapability,
        req: RoutingRequirement,
    ) -> tuple[bool, str]:
        """Check whether a model capability satisfies the routing requirements."""
        checks = [
            (req.tools_required and not cap.tools, "lacks tools capability"),
            (req.json_required and not cap.json_mode, "lacks json_mode capability"),
            (req.vision_required and not cap.vision, "lacks vision capability"),
            (req.audio_required and not cap.audio, "lacks audio capability"),
            (
                req.reasoning_required and not cap.reasoning,
                "lacks reasoning capability",
            ),
            (
                cap.context_window < req.min_context_window,
                f"context window {cap.context_window} < required {req.min_context_window}",
            ),
            (
                req.max_cost_per_token is not None
                and cap.input_cost_per_token > req.max_cost_per_token,
                f"cost {cap.input_cost_per_token} > max {req.max_cost_per_token}",
            ),
        ]
        for failed, reason in checks:
            if failed:
                return False, reason
        return True, "ok"

    def select_optimal_model(
        self,
        candidates: list[str],
        requirements: RoutingRequirement | None = None,
        strategy: RoutingStrategy | None = None,
    ) -> RoutingDecision:
        """Score candidate models and return the top-ranking model decision."""
        if not candidates:
            raise ValueError("No candidate models provided for routing.")

        strat = strategy or self.default_strategy
        req = requirements or RoutingRequirement()

        eligible: list[dict[str, Any]] = []
        for model in candidates:
            cap = detect_capabilities(model)
            ok, reason = self.satisfies_requirements(cap, req)
            cb = get_circuit_breaker(f"llm_{model}")

            circuit_open = cb.state == CircuitState.OPEN
            health = cb.health_score
            metrics = cb.get_health_metrics()

            eligible.append(
                {
                    "model": model,
                    "satisfies_reqs": ok,
                    "disqualify_reason": None if ok else reason,
                    "circuit_open": circuit_open,
                    "health_score": health,
                    "p50_latency_ms": metrics.get("p50_latency_ms", 100.0),
                    "input_cost": cap.input_cost_per_token,
                    "output_cost": cap.output_cost_per_token,
                    "avg_cost": (cap.input_cost_per_token + cap.output_cost_per_token)
                    / 2.0,
                    "context_window": cap.context_window,
                    "has_reasoning": cap.reasoning,
                }
            )

        # Filter candidates meeting hard capability criteria
        viable = [c for c in eligible if c["satisfies_reqs"] and not c["circuit_open"]]
        if not viable:
            # If all viable have open circuits, try those that meet reqs regardless of circuit
            viable = [c for c in eligible if c["satisfies_reqs"]]
            if not viable:
                # Fall back to first candidate
                return RoutingDecision(
                    selected_model=candidates[0],
                    strategy=strat,
                    score=0.0,
                    reason=f"No candidate met all requirements. Falling back to default: {candidates[0]}",
                    evaluated_candidates=eligible,
                )

        # Compute scoring for viable candidates
        for c in viable:
            score = 0.0
            health = c["health_score"]
            cost = c["avg_cost"]
            latency = c["p50_latency_ms"]

            # Normalized cost score (lower cost = higher score, capped)
            cost_score = 1.0 / (1.0 + cost * 100000.0)

            # Normalized latency score (lower latency = higher score)
            latency_score = 1000.0 / (1000.0 + latency)

            if strat == RoutingStrategy.COST_OPTIMIZED:
                score = 0.7 * cost_score + 0.3 * health
            elif strat == RoutingStrategy.LATENCY_OPTIMIZED:
                score = 0.6 * latency_score + 0.4 * health
            elif strat == RoutingStrategy.QUALITY_OPTIMIZED:
                quality_bonus = (0.3 if c["has_reasoning"] else 0.0) + min(
                    0.3, c["context_window"] / 500000.0
                )
                score = 0.4 * health + quality_bonus + 0.2 * latency_score
            else:  # BALANCED
                score = 0.4 * health + 0.3 * cost_score + 0.3 * latency_score

            c["score"] = round(score, 4)

        # Sort descending by score
        viable.sort(key=lambda x: x["score"], reverse=True)
        winner = viable[0]

        return RoutingDecision(
            selected_model=winner["model"],
            strategy=strat,
            score=winner["score"],
            reason=(
                f"Selected '{winner['model']}' via {strat.value} "
                f"(score: {winner['score']}, health: {winner['health_score']}, "
                f"avg_cost: ${winner['avg_cost']:.7f}/tok, latency: {winner['p50_latency_ms']}ms)"
            ),
            evaluated_candidates=eligible,
        )
