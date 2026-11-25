"""Budget service encapsulating tenant quota enforcement, spend tracking, and budget limits."""

from loguru import logger

from amberclaw.api.v1.budget import QuotaUsage, TenantQuotaManager


class BudgetService:
    """Service providing tenant token budget allocations, spending limits, and usage accounting."""

    def __init__(self, quota_manager: TenantQuotaManager | None = None) -> None:
        self.quota_manager = quota_manager or TenantQuotaManager.get_instance()

    def get_quota(self, tenant: str = "default") -> QuotaUsage:
        """Fetch current quota metrics and limits for the designated tenant."""
        return self.quota_manager.get_quota(tenant=tenant)

    def record_usage(self, tenant: str, tokens: int, cost: float) -> QuotaUsage:
        """Record token usage and financial cost, updating cumulative counters."""
        self.quota_manager.record_usage(tenant=tenant, tokens=tokens, cost=cost)
        quota = self.get_quota(tenant=tenant)
        logger.debug(
            "Recorded usage for tenant '{}': +{} tokens, +${:.4f} (total: {} / ${:.4f})",
            tenant,
            tokens,
            cost,
            quota.tokens_used,
            quota.spent_usd,
        )
        return quota

    def update_budget(
        self,
        tenant: str,
        max_tokens: int,
        max_budget_usd: float,
    ) -> QuotaUsage:
        """Update ceiling allocations for tokens and dollar budget for a tenant."""
        quota = self.quota_manager.update_budget(
            tenant=tenant,
            max_tokens=max_tokens,
            max_budget_usd=max_budget_usd,
        )
        logger.info(
            "Updated budget for tenant '{}': max_tokens={}, max_budget_usd=${:.2f}",
            tenant,
            max_tokens,
            max_budget_usd,
        )
        return quota
