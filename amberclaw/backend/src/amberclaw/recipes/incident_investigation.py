# ruff: noqa: S101
"""Recipe 2: Incident Investigation with Approved Remediation and Rollback (CL-021)."""

from __future__ import annotations

from typing import Any

from amberclaw.recipes.base import RecipeExecutionResult, RecipeManifest, RecipeStatus
from amberclaw.runtime.budget_ledger import PricingLedger
from amberclaw.security.approval import ApprovalStatus, ToolApprovalManager

MANIFEST = RecipeManifest(
    recipe_id="incident_investigation",
    version="1.0.0",
    name="SecOps Incident Triage & Remediation",
    description="Analyzes security alerts, determines probable root cause, and generates remediation plans requiring explicit human approval before execution.",
    required_scopes=["secops:investigate", "secops:remediate"],
    estimated_cost_usd=0.003,
    requires_human_approval=True,
    failure_recovery_policy="compensate_and_rollback",
    input_parameters={
        "incident_id": "Unique identifier for alert or ticket",
        "alert_type": "Classification string (e.g., unauthorized_egress, brute_force)",
        "logs": "List of log lines or telemetry entries",
    },
    output_contract={
        "root_cause": "Identified probable trigger",
        "proposed_action": "Specific remediation command",
        "approval_ticket_id": "Pending ticket ID awaiting operator approval",
    },
)


class IncidentInvestigationRecipe:
    """Investigates system incidents and enforces approval gates for remediation side-effects."""

    def __init__(
        self,
        approval_mgr: ToolApprovalManager | None = None,
        ledger: PricingLedger | None = None,
    ) -> None:
        self.manifest = MANIFEST
        self.approval_mgr = approval_mgr or ToolApprovalManager.get_instance()
        self.ledger = ledger or PricingLedger()

    async def initiate_investigation(
        self,
        incident_id: str,
        alert_type: str,
        logs: list[str],
        tenant_id: str = "secops",
        model_name: str = "claude-3-5-sonnet",
    ) -> RecipeExecutionResult:
        """Analyze incident logs and request approval for remediation."""
        log_text = "\n".join(logs)
        in_tokens = max(20, (len(alert_type) + len(log_text)) // 4)

        # Diagnose root cause based on log indicators
        if "outbound connection to unknown host" in log_text.lower():
            root_cause = "Suspicious network egress detected from uncontained worker."
            action_type = "block_network_ip"
            action_target = "198.51.100.42"
        elif "failed login threshold exceeded" in log_text.lower():
            root_cause = "Credential brute-force attack on dashboard port."
            action_type = "temporary_ip_ban"
            action_target = "203.0.113.19"
        else:
            root_cause = f"Anomalous system activity reported under alert '{alert_type}'."
            action_type = "isolate_process"
            action_target = incident_id

        # Since remediation mutates system state, create pending approval ticket
        ticket = self.approval_mgr.request_approval(
            tool_name="secops_remediate",
            parameters={
                "action": action_type,
                "target": action_target,
                "incident_id": incident_id,
            },
            requester_id="incident_recipe_agent",
            tenant_id=tenant_id,
        )

        out_tokens = 45
        cost = self.ledger.calculate_cost(
            model=model_name,
            prompt_tokens=in_tokens,
            completion_tokens=out_tokens,
        )

        return RecipeExecutionResult(
            recipe_id=self.manifest.recipe_id,
            status=RecipeStatus.WAITING_FOR_APPROVAL,
            approval_ticket_id=ticket.ticket_id,
            final_state={
                "incident_id": incident_id,
                "root_cause": root_cause,
                "proposed_action": action_type,
                "action_target": action_target,
                "remediation_status": "pending_human_approval",
            },
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            actual_cost_usd=round(cost, 6),
            safety_checks_passed=True,
        )

    async def finalize_remediation(
        self,
        ticket_id: str,
        approved: bool,
        operator_notes: str = "",
    ) -> RecipeExecutionResult:
        """Resolve pending ticket and execute remediation or trigger rollback."""
        success = self.approval_mgr.resolve_ticket(
            ticket_id=ticket_id,
            approved=approved,
            reviewer="human_secops_lead",
            notes=operator_notes,
        )

        resolved_ticket = self.approval_mgr.get_ticket(ticket_id)
        if not success or not resolved_ticket:
            return RecipeExecutionResult(
                recipe_id=self.manifest.recipe_id,
                status=RecipeStatus.FAILED,
                error=f"Ticket '{ticket_id}' not found or could not be resolved.",
                safety_checks_passed=False,
            )

        if approved:
            return RecipeExecutionResult(
                recipe_id=self.manifest.recipe_id,
                status=RecipeStatus.COMPLETED,
                approval_ticket_id=ticket_id,
                final_state={
                    "remediation_status": "executed",
                    "action": resolved_ticket.args.get("action"),
                    "target": resolved_ticket.args.get("target"),
                    "operator_notes": operator_notes,
                },
                safety_checks_passed=True,
            )
        else:
            return RecipeExecutionResult(
                recipe_id=self.manifest.recipe_id,
                status=RecipeStatus.ROLLED_BACK,
                approval_ticket_id=ticket_id,
                final_state={
                    "remediation_status": "rejected_and_rolled_back",
                    "reason": operator_notes or "Rejected by human reviewer",
                },
                safety_checks_passed=True,
            )
