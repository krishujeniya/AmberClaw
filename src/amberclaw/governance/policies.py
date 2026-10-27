"""Declarative governance policies and rule evaluation engine."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EnforcementAction(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    WARN = "warn"


class PolicyRule(BaseModel):
    """A governance policy rule."""

    policy_id: str = Field(..., description="Unique policy identifier.")
    name: str = Field(..., description="Human-readable policy name.")
    description: str = ""
    target_actions: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Glob patterns or action names this policy governs.",
    )
    max_cost: float | None = Field(default=None, description="Maximum allowable USD cost.")
    forbidden_tokens: list[str] = Field(
        default_factory=list,
        description="Tokens or substrings that trigger denial/approval if found.",
    )
    enforcement: EnforcementAction = Field(default=EnforcementAction.REQUIRE_APPROVAL)
    enabled: bool = True


class PolicyEvaluationResult(BaseModel):
    """Result of policy evaluation against a proposed action."""

    is_allowed: bool
    requires_approval: bool = False
    enforcement: EnforcementAction = EnforcementAction.ALLOW
    triggered_policies: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class PolicyEngine:
    """Evaluates agent proposals and actions against active governance policies."""

    def __init__(self) -> None:
        self._policies: dict[str, PolicyRule] = {}
        self._load_default_policies()

    def _load_default_policies(self) -> None:
        self.add_policy(
            PolicyRule(
                policy_id="POL-001-ROOT-EXEC",
                name="Deny Root Execution",
                description="Forbids running commands as root or with sudo without explicit sign-off.",
                target_actions=["bash", "exec", "terminal"],
                forbidden_tokens=["sudo ", "su -", "root@"],
                enforcement=EnforcementAction.DENY,
            )
        )
        self.add_policy(
            PolicyRule(
                policy_id="POL-002-COST-LIMIT",
                name="Enforce Max Single Turn Cost",
                description="Requires approval for actions exceeding cost threshold.",
                target_actions=["*"],
                max_cost=5.0,
                enforcement=EnforcementAction.REQUIRE_APPROVAL,
            )
        )
        self.add_policy(
            PolicyRule(
                policy_id="POL-003-PROD-DEPLOY",
                name="Require Human Approval For Production Deploys",
                description="Production deploy commands require human review.",
                target_actions=["deploy", "git", "bash"],
                forbidden_tokens=["deploy:prod", "production", "main --force"],
                enforcement=EnforcementAction.REQUIRE_APPROVAL,
            )
        )

    def add_policy(self, policy: PolicyRule) -> None:
        """Register or update a policy rule."""
        self._policies[policy.policy_id] = policy

    def remove_policy(self, policy_id: str) -> bool:
        """Remove a policy rule by ID."""
        return self._policies.pop(policy_id, None) is not None

    def list_policies(self) -> list[PolicyRule]:
        """List all active policies."""
        return list(self._policies.values())

    def evaluate(
        self,
        action_name: str,
        content: str = "",
        cost_estimate: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> PolicyEvaluationResult:
        """Evaluate action parameters against enabled policy rules."""
        _ = metadata
        triggered: list[str] = []
        reasons: list[str] = []
        final_enforcement = EnforcementAction.ALLOW

        for p in self._policies.values():
            if not p.enabled:
                continue

            # Check action target match
            action_matches = "*" in p.target_actions or any(
                a.lower() == action_name.lower() for a in p.target_actions
            )
            if not action_matches:
                continue

            content_lower = content.lower()
            token_hit = any(t.lower() in content_lower for t in p.forbidden_tokens)
            cost_hit = p.max_cost is not None and cost_estimate > p.max_cost
            has_constraints = bool(p.forbidden_tokens) or (p.max_cost is not None)

            should_trigger = False
            if not has_constraints or token_hit or cost_hit:
                should_trigger = True

            if should_trigger:
                triggered.append(p.policy_id)
                reason = f"Triggered {p.name}"
                if token_hit:
                    reason += f" (Forbidden token matched in '{action_name}')"
                if cost_hit:
                    reason += f" (Cost ${cost_estimate} exceeds max ${p.max_cost})"
                reasons.append(reason)

                # Prioritize DENY over REQUIRE_APPROVAL over WARN
                if p.enforcement == EnforcementAction.DENY:
                    final_enforcement = EnforcementAction.DENY
                elif p.enforcement == EnforcementAction.REQUIRE_APPROVAL and final_enforcement != EnforcementAction.DENY:
                    final_enforcement = EnforcementAction.REQUIRE_APPROVAL
                elif p.enforcement == EnforcementAction.WARN and final_enforcement == EnforcementAction.ALLOW:
                    final_enforcement = EnforcementAction.WARN

        is_allowed = final_enforcement != EnforcementAction.DENY
        requires_approval = final_enforcement == EnforcementAction.REQUIRE_APPROVAL

        return PolicyEvaluationResult(
            is_allowed=is_allowed,
            requires_approval=requires_approval,
            enforcement=final_enforcement,
            triggered_policies=triggered,
            reasons=reasons,
        )
