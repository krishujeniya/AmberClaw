# ruff: noqa: S101
"""Recipe 3: Scheduled Operations & Budget Report with Approved Delivery (CL-021)."""

from __future__ import annotations

from typing import Any

from amberclaw.recipes.base import RecipeExecutionResult, RecipeManifest, RecipeStatus
from amberclaw.runtime.budget_ledger import PricingLedger
from amberclaw.security.approval import ApprovalStatus, ToolApprovalManager

MANIFEST = RecipeManifest(
    recipe_id="scheduled_report",
    version="1.0.0",
    name="Scheduled Operations & Budget Report",
    description="Compiles periodic operational metrics, resource utilization, and cost breakdowns, gating external distribution behind human sign-off.",
    required_scopes=["reports:generate", "reports:distribute"],
    estimated_cost_usd=0.002,
    requires_human_approval=True,
    failure_recovery_policy="abort_on_delivery_failure",
    input_parameters={
        "report_period": "String defining time window (e.g., '2026-W45', '2026-10')",
        "metrics": "Dictionary of key performance metrics (runs, latency, spend)",
        "destination_channel": "Delivery route (e.g. 'internal_email', 'ops_channel')",
    },
    output_contract={
        "report_content": "Rendered markdown executive summary",
        "delivery_status": "Status of report dispatch",
        "approval_ticket_id": "Pending approval ticket for external delivery",
    },
)


class ScheduledReportRecipe:
    """Compiles operational health and spend reports, ensuring delivery approval."""

    def __init__(
        self,
        approval_mgr: ToolApprovalManager | None = None,
        ledger: PricingLedger | None = None,
    ) -> None:
        self.manifest = MANIFEST
        self.approval_mgr = approval_mgr or ToolApprovalManager.get_instance()
        self.ledger = ledger or PricingLedger()

    async def compile_report(
        self,
        report_period: str,
        metrics: dict[str, Any],
        destination_channel: str,
        tenant_id: str = "operations",
        require_approval_before_send: bool = True,
        model_name: str = "claude-3-5-sonnet",
    ) -> RecipeExecutionResult:
        """Compile executive report and gate delivery."""
        total_runs = metrics.get("total_runs", 0)
        successful_runs = metrics.get("successful_runs", 0)
        spend_usd = metrics.get("total_spend_usd", 0.0)
        p95_latency = metrics.get("p95_latency_ms", 0.0)

        success_rate = (
            (successful_runs / total_runs * 100.0) if total_runs > 0 else 100.0
        )

        report_markdown = (
            f"# Operational & Budget Summary ({report_period})\n\n"
            f"- **Total Workflow Runs:** {total_runs}\n"
            f"- **Success Rate:** {success_rate:.1f}%\n"
            f"- **P95 Latency:** {p95_latency:.1f} ms\n"
            f"- **Total Recorded Spend:** ${spend_usd:.4f}\n"
        )

        in_tokens = max(15, len(str(metrics)) // 4)
        out_tokens = max(20, len(report_markdown) // 4)
        cost = self.ledger.calculate_cost(
            model=model_name,
            prompt_tokens=in_tokens,
            completion_tokens=out_tokens,
        )

        if require_approval_before_send:
            ticket = self.approval_mgr.request_approval(
                tool_name="dispatch_external_report",
                parameters={
                    "period": report_period,
                    "channel": destination_channel,
                    "preview_chars": len(report_markdown),
                },
                requester_id="report_scheduler_agent",
                tenant_id=tenant_id,
            )
            return RecipeExecutionResult(
                recipe_id=self.manifest.recipe_id,
                status=RecipeStatus.WAITING_FOR_APPROVAL,
                approval_ticket_id=ticket.ticket_id,
                final_state={
                    "period": report_period,
                    "report_markdown": report_markdown,
                    "delivery_status": "awaiting_approval_to_send",
                    "destination": destination_channel,
                },
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                actual_cost_usd=round(cost, 6),
                safety_checks_passed=True,
            )
        else:
            return RecipeExecutionResult(
                recipe_id=self.manifest.recipe_id,
                status=RecipeStatus.COMPLETED,
                final_state={
                    "period": report_period,
                    "report_markdown": report_markdown,
                    "delivery_status": "dispatched",
                    "destination": destination_channel,
                },
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                actual_cost_usd=round(cost, 6),
                safety_checks_passed=True,
            )

    async def approve_and_dispatch(
        self,
        ticket_id: str,
        approved: bool,
    ) -> RecipeExecutionResult:
        """Process operator decision for report delivery."""
        success = self.approval_mgr.resolve_ticket(
            ticket_id=ticket_id,
            approved=approved,
            reviewer="human_operations_lead",
        )
        if not success:
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
                final_state={"delivery_status": "dispatched_to_channel"},
                safety_checks_passed=True,
            )
        else:
            return RecipeExecutionResult(
                recipe_id=self.manifest.recipe_id,
                status=RecipeStatus.ROLLED_BACK,
                approval_ticket_id=ticket_id,
                final_state={"delivery_status": "dispatch_suppressed_by_operator"},
                safety_checks_passed=True,
            )
