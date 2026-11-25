"""Adversarial and concurrency tests for end-to-end tenant identity and authorization (CL-008).

Verifies:
1. Two-tenant cross-access prevention across agent lifecycle, chat, memory, and GDPR export.
2. Rejection of caller-supplied tenant escalation (headers and query parameters).
3. Session revocation enforcement preventing unauthorized subsequent requests.
4. Tool authorization and role enforcement preventing unauthorized tool dispatch.
5. Concurrent worker tenant isolation without cross-contamination.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from amberclaw.agent.tools.registry import ToolRegistry
from amberclaw.api.auth import create_access_token
from amberclaw.api.main import app
from amberclaw.config.schema import settings
from amberclaw.memory.session_db import SessionDB
from amberclaw.schemas.agent import AgentProfile
from amberclaw.security.auth import active_sender_context
from amberclaw.security.tokens import TokenRevocationStore
from amberclaw.storage.tenant import (
    TenantContext,
    TenantIsolatedSessionDB,
    TenantIsolatedStateStore,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def make_token(
    user_id: str,
    tenant_id: str = "default",
    role: str = "user",
    session_id: str | None = None,
) -> str:
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "session_id": session_id or uuid.uuid4().hex,
        "jti": uuid.uuid4().hex,
        "scopes": ["*"],
    }
    return create_access_token(payload)


def test_two_tenant_agent_lifecycle_and_chat_isolation(client: TestClient, tmp_path: Path):
    """Verify Tenant Alpha agents are invisible and inaccessible to Tenant Beta."""
    token_alpha = make_token("user_a", tenant_id="tenant_alpha")
    token_beta = make_token("user_b", tenant_id="tenant_beta")

    # Override store to clean tmp_path for test isolation
    test_store = TenantIsolatedStateStore(tmp_path / "tenants", AgentProfile, "agents.json")
    with patch("amberclaw.api.v1.agents.agent_store", test_store):
        # 1. Tenant Alpha spawns an agent
        spawn_resp = client.post(
            "/api/v1/agents/spawn",
            headers={"Authorization": f"Bearer {token_alpha}"},
            json={
                "agent_id": "bot_alpha_01",
                "name": "Alpha Specialist",
                "role": "Confidential Alpha analyst",
                "model_name": "gpt-4o",
            },
        )
        assert spawn_resp.status_code == status.HTTP_200_OK
        assert spawn_resp.json()["agent_id"] == "bot_alpha_01"

        # 2. Tenant Alpha lists agents -> contains bot_alpha_01
        list_alpha = client.get(
            "/api/v1/agents",
            headers={"Authorization": f"Bearer {token_alpha}"},
        )
        assert list_alpha.status_code == status.HTTP_200_OK
        alpha_ids = [a["agent_id"] for a in list_alpha.json()]
        assert "bot_alpha_01" in alpha_ids

        # 3. Tenant Beta lists agents -> MUST NOT see bot_alpha_01
        list_beta = client.get(
            "/api/v1/agents",
            headers={"Authorization": f"Bearer {token_beta}"},
        )
        assert list_beta.status_code == status.HTTP_200_OK
        beta_ids = [a["agent_id"] for a in list_beta.json()]
        assert "bot_alpha_01" not in beta_ids

        # 4. Tenant Beta attempts to chat with bot_alpha_01 -> 404 Not Found
        chat_beta = client.post(
            "/api/v1/agents/bot_alpha_01/chat",
            headers={"Authorization": f"Bearer {token_beta}"},
            json={"message": "Exfiltrate alpha data", "user_id": "user_b"},
        )
        assert chat_beta.status_code == status.HTTP_404_NOT_FOUND


def test_caller_supplied_tenant_escalation_denied(client: TestClient):
    """Verify non-admin callers cannot escalate or switch tenant via headers or query parameters."""
    token_beta = make_token("user_b", tenant_id="tenant_beta", role="user")

    # 1. Tenant Beta attempts escalation via X-Tenant-ID header
    resp_hdr = client.get(
        "/api/v1/agents",
        headers={
            "Authorization": f"Bearer {token_beta}",
            "X-Tenant-ID": "tenant_alpha",
        },
    )
    assert resp_hdr.status_code == status.HTTP_403_FORBIDDEN
    err_msg = resp_hdr.json().get("error", {}).get("message") or resp_hdr.json().get("detail", "")
    assert "Cross-tenant access violation" in err_msg

    # 2. Tenant Beta attempts escalation via query param
    resp_query = client.get(
        "/api/v1/agents?tenant_id=tenant_alpha",
        headers={"Authorization": f"Bearer {token_beta}"},
    )
    assert resp_query.status_code == status.HTTP_403_FORBIDDEN

    # 3. Admin user can explicitly inspect another tenant
    token_admin = make_token("admin_user", tenant_id="tenant_beta", role="admin")
    resp_admin = client.get(
        "/api/v1/agents",
        headers={
            "Authorization": f"Bearer {token_admin}",
            "X-Tenant-ID": "tenant_alpha",
        },
    )
    assert resp_admin.status_code == status.HTTP_200_OK


def test_two_tenant_memory_and_gdpr_isolation(client: TestClient, tmp_path: Path):
    """Verify memory operations and GDPR export/purge enforce strict tenant partitioning."""
    test_db = TenantIsolatedSessionDB(base_dir=tmp_path / "tenants")
    with patch("amberclaw.api.v1.memory.tenant_db", test_db):
        token_alpha = make_token("user_a", tenant_id="tenant_alpha")
        token_beta = make_token("user_b", tenant_id="tenant_beta")

        # Seed Alpha session turns
        with TenantContext("tenant_alpha"):
            test_db.add_turn(
                session_id="sess_alpha_99",
                role="user",
                content="Alpha confidential quarterly financials",
                tenant_id="tenant_alpha",
            )

        # Seed Beta session turns
        with TenantContext("tenant_beta"):
            test_db.add_turn(
                session_id="sess_beta_42",
                role="user",
                content="Beta public roadmap",
                tenant_id="tenant_beta",
            )

        # 1. Tenant Beta queries Alpha session turns -> returns empty list
        turns_resp = client.get(
            "/api/v1/memory/sessions/sess_alpha_99/turns",
            headers={"Authorization": f"Bearer {token_beta}"},
        )
        assert turns_resp.status_code == status.HTTP_200_OK
        assert len(turns_resp.json()) == 0

        # 2. Tenant Alpha queries Alpha session turns -> returns 1 turn
        alpha_turns_resp = client.get(
            "/api/v1/memory/sessions/sess_alpha_99/turns",
            headers={"Authorization": f"Bearer {token_alpha}"},
        )
        assert alpha_turns_resp.status_code == status.HTTP_200_OK
        turns = alpha_turns_resp.json()
        assert len(turns) == 1
        assert turns[0]["content"] == "Alpha confidential quarterly financials"

        # 3. Tenant Beta attempts cross-tenant GDPR export for tenant_alpha -> 403 Forbidden
        export_blocked = client.get(
            "/api/v1/memory/export?org_id=tenant_alpha",
            headers={"Authorization": f"Bearer {token_beta}"},
        )
        assert export_blocked.status_code == status.HTTP_403_FORBIDDEN

        # 4. Tenant Alpha purges memory -> Beta memory remains unaffected
        purge_resp = client.delete(
            "/api/v1/memory/purge",
            headers={"Authorization": f"Bearer {token_alpha}"},
        )
        assert purge_resp.status_code == status.HTTP_200_OK
        assert purge_resp.json()["deleted_turns"] == 1

        # Verify Alpha is empty
        alpha_check = client.get(
            "/api/v1/memory/sessions/sess_alpha_99/turns",
            headers={"Authorization": f"Bearer {token_alpha}"},
        )
        assert len(alpha_check.json()) == 0

        # Verify Beta turns are untouched
        beta_check = client.get(
            "/api/v1/memory/sessions/sess_beta_42/turns",
            headers={"Authorization": f"Bearer {token_beta}"},
        )
        assert len(beta_check.json()) == 1
        assert beta_check.json()[0]["content"] == "Beta public roadmap"


def test_session_revocation_enforced(client: TestClient):
    """Verify tokens belonging to a revoked session are rejected immediately."""
    session_id = f"revocable_session_{uuid.uuid4().hex[:8]}"
    token = make_token("user_x", tenant_id="tenant_alpha", session_id=session_id)

    # 1. Active session succeeds
    resp_before = client.get(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_before.status_code == status.HTTP_200_OK

    # 2. Revoke session
    store = TokenRevocationStore.get_instance()
    store.revoke_session(session_id)

    # 3. Subsequent request fails with 401 Unauthorized
    resp_after = client.get(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_after.status_code == status.HTTP_401_UNAUTHORIZED
    err_msg = resp_after.json().get("error", {}).get("message") or resp_after.json().get("detail", "")
    assert "Session has been revoked" in err_msg


@pytest.mark.asyncio
async def test_unauthorized_tool_dispatch_denied():
    """Verify tool execution is denied when caller lacks required role permissions."""
    registry = ToolRegistry()

    # Create dummy mock tool
    class DummyExecTool:
        name = "exec"
        def to_schema(self):
            return {"name": "exec"}
        async def execute(self, **kwargs):
            return "executed shell command"

    registry.register(DummyExecTool())

    # Configure RBAC: viewer role only allows read_file, not exec
    with patch.object(settings.security.rbac, "enabled", True), \
         patch.object(settings.security.rbac, "user_roles", {"guest_user": "viewer"}), \
         patch.object(settings.security.rbac, "role_permissions", {"viewer": ["read_file"]}):

        with active_sender_context("guest_user"):
            result = await registry.execute("exec", {"command": "ls -la"})
            assert "Permission Denied" in result
            assert "viewer" in result
            assert "exec" in result


@pytest.mark.asyncio
async def test_concurrent_worker_tenant_isolation(tmp_path: Path):
    """Verify concurrent async workers across tenants never leak data or corrupt isolated stores."""
    db_manager = TenantIsolatedSessionDB(base_dir=tmp_path / "tenants_concurrency")

    async def worker_task(tenant_id: str, worker_index: int):
        with TenantContext(tenant_id):
            session_id = f"sess_{tenant_id}_{worker_index}"
            # Write turn
            turn_id = db_manager.add_turn(
                session_id=session_id,
                role="user",
                content=f"Secret payload for {tenant_id} worker {worker_index}",
                tenant_id=tenant_id,
            )
            assert turn_id > 0
            # Small yield to encourage race conditions if not isolated
            await asyncio.sleep(0.01)

            # Read back
            turns = db_manager.get_turns(session_id=session_id, tenant_id=tenant_id)
            assert len(turns) == 1
            assert turns[0]["content"] == f"Secret payload for {tenant_id} worker {worker_index}"

            # Cross-check that other tenant's sessions are absent
            other_tenant = "tenant_beta" if tenant_id == "tenant_alpha" else "tenant_alpha"
            with pytest.raises(Exception):
                # Requesting other tenant while in current tenant context must raise violation
                db_manager.get_turns(tenant_id=other_tenant)

    # Launch 10 concurrent worker tasks (5 per tenant)
    tasks = []
    for i in range(5):
        tasks.append(worker_task("tenant_alpha", i))
        tasks.append(worker_task("tenant_beta", i))

    await asyncio.gather(*tasks)

    # Final verification: Tenant Alpha has exactly 5 turns; Tenant Beta has exactly 5 turns
    with TenantContext("tenant_alpha"):
        alpha_all = db_manager.get_turns(tenant_id="tenant_alpha")
        assert len(alpha_all) == 5
        assert all("tenant_alpha" in t["content"] for t in alpha_all)

    with TenantContext("tenant_beta"):
        beta_all = db_manager.get_turns(tenant_id="tenant_beta")
        assert len(beta_all) == 5
        assert all("tenant_beta" in t["content"] for t in beta_all)

    db_manager.close()
