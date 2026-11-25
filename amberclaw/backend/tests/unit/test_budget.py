# ruff: noqa: PLR2004, S105
"""Unit tests for Section 15 API & SDK Maturity:
- Webhook HMAC-SHA256 signing, verification, and replay protection
- Optimistic concurrency control and ETag verification
- Tenant token budget, spending quotas, and usage management
- API budget router endpoints with ETag & If-Match concurrency checks
"""

import time

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from amberclaw.api.concurrency import generate_etag, verify_if_match
from amberclaw.api.v1.budget import (
    TenantQuotaManager,
)
from amberclaw.api.v1.budget import (
    router as budget_router,
)
from amberclaw.api.webhooks import (
    WebhookSecurityError,
    WebhookSigner,
    WebhookVerifier,
)


@pytest.fixture(autouse=True)
def reset_budget_manager():
    TenantQuotaManager.get_instance().clear()
    yield
    TenantQuotaManager.get_instance().clear()


# ==============================================================================
# 1. Webhook HMAC-SHA256 Signing & Replay Protection
# ==============================================================================


def test_webhook_signing_and_verification_happy_path():
    secret = "whsec_super_secret_webhook_key_123"
    signer = WebhookSigner(secret)
    verifier = WebhookVerifier(secret, tolerance_seconds=300)

    payload = '{"event": "agent.completed", "agent_id": "agent_alpha", "tokens": 150}'
    sig_header = signer.sign_payload(payload)

    assert sig_header.startswith("t=")
    assert ",v1=" in sig_header

    # Verify signature passes
    assert verifier.verify_payload(payload, sig_header) is True


def test_webhook_tampered_payload_rejected():
    secret = "whsec_super_secret_webhook_key_123"
    signer = WebhookSigner(secret)
    verifier = WebhookVerifier(secret, tolerance_seconds=300)

    payload = '{"event": "agent.completed", "amount": 100}'
    sig_header = signer.sign_payload(payload)

    tampered_payload = '{"event": "agent.completed", "amount": 999999}'
    with pytest.raises(WebhookSecurityError) as exc_info:
        verifier.verify_payload(tampered_payload, sig_header)
    assert "Invalid webhook signature" in str(exc_info.value)


def test_webhook_replay_attack_rejected_outside_tolerance():
    secret = "whsec_super_secret_webhook_key_123"
    signer = WebhookSigner(secret)
    verifier = WebhookVerifier(secret, tolerance_seconds=60)

    payload = '{"event": "payment.processed"}'
    # Timestamp from 10 minutes ago
    old_timestamp = int(time.time()) - 600
    sig_header = signer.sign_payload(payload, timestamp=old_timestamp)

    with pytest.raises(WebhookSecurityError) as exc_info:
        verifier.verify_payload(payload, sig_header)
    assert "outside tolerance window" in str(exc_info.value)


# ==============================================================================
# 2. Optimistic Concurrency & ETag Verification
# ==============================================================================


def test_generate_etag_deterministic():
    data1 = {"id": "res_1", "version": 2, "name": "Agent A"}
    data2 = {"name": "Agent A", "id": "res_1", "version": 2}

    etag1 = generate_etag(data1)
    etag2 = generate_etag(data2)

    assert etag1.startswith('W/"')
    assert etag1 == etag2


def test_verify_if_match_success_and_wildcard():
    current_etag = 'W/"abcd1234efgh5678"'

    # Exact match passes
    verify_if_match('W/"abcd1234efgh5678"', current_etag)

    # Wildcard passes
    verify_if_match("*", current_etag)

    # Missing header passes (unconditional update)
    verify_if_match(None, current_etag)


def test_verify_if_match_mismatch_raises_412():
    current_etag = 'W/"current_version_123"'
    stale_etag = 'W/"stale_version_000"'

    with pytest.raises(HTTPException) as exc_info:
        verify_if_match(stale_etag, current_etag)

    assert exc_info.value.status_code == 412
    assert "Precondition Failed" in exc_info.value.detail


# ==============================================================================
# 3. Tenant Quota & Budget Manager
# ==============================================================================


def test_tenant_quota_manager_usage_and_update():
    mgr = TenantQuotaManager.get_instance()

    quota = mgr.get_quota("tenant_acme")
    assert quota.tenant == "tenant_acme"
    assert quota.tokens_used == 0

    mgr.record_usage("tenant_acme", tokens=2500, cost=0.05)
    updated = mgr.get_quota("tenant_acme")
    assert updated.tokens_used == 2500
    assert updated.spent_usd == 0.05
    assert updated.requests_count == 1

    # Update budget
    modified = mgr.update_budget("tenant_acme", max_tokens=500000, max_budget_usd=25.0)
    assert modified.max_tokens_limit == 500000
    assert modified.max_budget_usd == 25.0
    assert modified.version == 2

    # Reset
    reset = mgr.reset_usage("tenant_acme")
    assert reset.tokens_used == 0
    assert reset.spent_usd == 0.0
    assert reset.version == 3


# ==============================================================================
# 4. Budget API Endpoints (FastAPI TestClient)
# ==============================================================================


@pytest.fixture
def budget_client():
    app = FastAPI()
    app.include_router(budget_router, prefix="/api/v1/budget")
    return TestClient(app)


def test_api_get_budget_returns_etag(budget_client):
    res = budget_client.get("/api/v1/budget?tenant=corp_alpha")
    assert res.status_code == 200
    assert "ETag" in res.headers
    assert res.headers["Cache-Control"] == "no-cache"

    data = res.json()
    assert data["tenant"] == "corp_alpha"
    assert data["max_tokens_limit"] == 1000000


def test_api_update_budget_with_optimistic_concurrency(budget_client):
    # 1. Fetch current resource to obtain ETag
    get_res = budget_client.get("/api/v1/budget?tenant=corp_beta")
    assert get_res.status_code == 200
    etag = get_res.headers["ETag"]

    # 2. Update with matching If-Match succeeds
    put_res = budget_client.put(
        "/api/v1/budget?tenant=corp_beta",
        json={"max_tokens_limit": 2000000, "max_budget_usd": 100.0},
        headers={"If-Match": etag},
    )
    assert put_res.status_code == 200
    new_data = put_res.json()
    assert new_data["max_tokens_limit"] == 2000000
    new_etag = put_res.headers["ETag"]
    assert new_etag != etag

    # 3. Attempt update with old/stale ETag fails with 412 Precondition Failed
    stale_res = budget_client.put(
        "/api/v1/budget?tenant=corp_beta",
        json={"max_tokens_limit": 3000000, "max_budget_usd": 150.0},
        headers={"If-Match": etag},  # Stale ETag!
    )
    assert stale_res.status_code == 412
    assert "Precondition Failed" in stale_res.json()["detail"]


def test_api_reset_budget(budget_client):
    # Seed usage
    mgr = TenantQuotaManager.get_instance()
    mgr.record_usage("corp_gamma", tokens=5000, cost=0.1)

    res = budget_client.post("/api/v1/budget/reset?tenant=corp_gamma")
    assert res.status_code == 200
    data = res.json()
    assert data["tokens_used"] == 0
    assert data["spent_usd"] == 0.0
