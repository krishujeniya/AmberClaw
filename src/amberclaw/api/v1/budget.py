"""API Quota, Token Budget, and Spending Limit Endpoints with Optimistic Concurrency."""

from typing import Annotated

from fastapi import APIRouter, Header, Response
from pydantic import BaseModel, Field

from amberclaw.api.concurrency import generate_etag, verify_if_match

router = APIRouter()


class QuotaUsage(BaseModel):
    """Token budget, request quotas, and spending metrics for a tenant."""

    tenant: str
    max_tokens_limit: int = 1000000
    tokens_used: int = 0
    max_budget_usd: float = 50.0
    spent_usd: float = 0.0
    requests_count: int = 0
    version: int = 1


class UpdateBudgetRequest(BaseModel):
    max_tokens_limit: int = Field(ge=1000)
    max_budget_usd: float = Field(ge=0.0)


class TenantQuotaManager:
    """In-memory thread-safe quota and budget tracker per tenant."""

    _instance: "TenantQuotaManager | None" = None

    def __init__(self) -> None:
        self._quotas: dict[str, QuotaUsage] = {}

    @classmethod
    def get_instance(cls) -> "TenantQuotaManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_quota(self, tenant: str = "default") -> QuotaUsage:
        if tenant not in self._quotas:
            self._quotas[tenant] = QuotaUsage(tenant=tenant)
        return self._quotas[tenant]

    def record_usage(self, tenant: str, tokens: int, cost: float) -> None:
        quota = self.get_quota(tenant)
        quota.tokens_used += tokens
        quota.spent_usd = round(quota.spent_usd + cost, 4)
        quota.requests_count += 1

    def update_budget(
        self, tenant: str, max_tokens: int, max_budget_usd: float
    ) -> QuotaUsage:
        quota = self.get_quota(tenant)
        quota.max_tokens_limit = max_tokens
        quota.max_budget_usd = max_budget_usd
        quota.version += 1
        return quota

    def reset_usage(self, tenant: str = "default") -> QuotaUsage:
        quota = self.get_quota(tenant)
        quota.tokens_used = 0
        quota.spent_usd = 0.0
        quota.requests_count = 0
        quota.version += 1
        return quota

    def clear(self) -> None:
        self._quotas.clear()


@router.get("", response_model=QuotaUsage)
async def get_budget(response: Response, tenant: str = "default") -> QuotaUsage:
    """Retrieve current token budget, spending limits, and usage with ETag."""
    mgr = TenantQuotaManager.get_instance()
    quota = mgr.get_quota(tenant)
    etag = generate_etag(quota.model_dump())
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "no-cache"
    return quota


@router.put("", response_model=QuotaUsage)
async def update_budget(
    request: UpdateBudgetRequest,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
    tenant: str = "default",
) -> QuotaUsage:
    """Update quota and budget limits enforcing optimistic concurrency via If-Match."""
    mgr = TenantQuotaManager.get_instance()
    current_quota = mgr.get_quota(tenant)

    # Concurrency check
    current_etag = generate_etag(current_quota.model_dump())
    verify_if_match(if_match, current_etag)

    updated = mgr.update_budget(
        tenant=tenant,
        max_tokens=request.max_tokens_limit,
        max_budget_usd=request.max_budget_usd,
    )
    new_etag = generate_etag(updated.model_dump())
    response.headers["ETag"] = new_etag
    return updated


@router.post("/reset", response_model=QuotaUsage)
async def reset_budget(response: Response, tenant: str = "default") -> QuotaUsage:
    """Reset token usage and spending metrics for a new billing window."""
    mgr = TenantQuotaManager.get_instance()
    quota = mgr.reset_usage(tenant)
    response.headers["ETag"] = generate_etag(quota.model_dump())
    return quota
