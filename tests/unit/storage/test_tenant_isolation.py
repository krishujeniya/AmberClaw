"""Unit tests for Multi-Tenant Storage Isolation."""

from pathlib import Path

import pytest
from pydantic import BaseModel

from amberclaw.storage.tenant import (
    CrossTenantAccessViolationError,
    TenantContext,
    TenantIsolatedSessionDB,
    TenantIsolatedStateStore,
)


class MockTenantItem(BaseModel):
    id: str
    name: str


def test_tenant_context_manager():
    assert TenantContext.get_current() is None
    with TenantContext("org_1"):
        assert TenantContext.get_current() == "org_1"
        assert TenantContext.require_current() == "org_1"
        with TenantContext("org_2"):
            assert TenantContext.get_current() == "org_2"
        assert TenantContext.get_current() == "org_1"
    assert TenantContext.get_current() is None

    with pytest.raises(CrossTenantAccessViolationError):
        TenantContext.require_current()


def test_tenant_isolated_session_db(tmp_path: Path):
    db_manager = TenantIsolatedSessionDB(base_dir=tmp_path / "tenants")

    # Tenant Alpha writes turn
    with TenantContext("tenant_alpha"):
        t1 = db_manager.add_turn(
            session_id="sess_alpha",
            role="user",
            content="Alpha confidential strategy",
        )
        assert t1 > 0
        turns_alpha = db_manager.get_turns(session_id="sess_alpha")
        assert len(turns_alpha) == 1
        assert turns_alpha[0]["content"] == "Alpha confidential strategy"

        # Search within tenant
        search_res = db_manager.search_turns("confidential")
        assert len(search_res) == 1
        assert search_res[0]["session_id"] == "sess_alpha"

    # Tenant Beta writes turn
    with TenantContext("tenant_beta"):
        t2 = db_manager.add_turn(
            session_id="sess_beta",
            role="user",
            content="Beta secret research project",
        )
        assert t2 > 0

        # Tenant Beta cannot see Tenant Alpha turns
        turns_beta = db_manager.get_turns()
        assert len(turns_beta) == 1
        assert turns_beta[0]["session_id"] == "sess_beta"

        # Search in Beta does not match Alpha confidential strategy
        search_res = db_manager.search_turns("confidential")
        assert len(search_res) == 0

    # Physical file verification
    alpha_file = tmp_path / "tenants" / "tenant_alpha" / "sessions.db"
    beta_file = tmp_path / "tenants" / "tenant_beta" / "sessions.db"
    assert alpha_file.exists()
    assert beta_file.exists()

    # Purge Tenant Alpha should not affect Tenant Beta
    with TenantContext("tenant_alpha"):
        deleted = db_manager.purge_tenant_memory()
        assert deleted == 1
        assert len(db_manager.get_turns()) == 0

    with TenantContext("tenant_beta"):
        assert len(db_manager.get_turns()) == 1

    db_manager.close()


def test_cross_tenant_access_violation(tmp_path: Path):
    db_manager = TenantIsolatedSessionDB(base_dir=tmp_path / "tenants")

    # Attempting access without context or tenant parameter
    with pytest.raises(CrossTenantAccessViolationError):
        db_manager.get_turns()

    # In Tenant A context, attempting to query Tenant B
    with TenantContext("tenant_a"):
        with pytest.raises(CrossTenantAccessViolationError):
            db_manager.get_turns(tenant_id="tenant_b")

        with pytest.raises(CrossTenantAccessViolationError):
            db_manager.add_turn(
                session_id="sess",
                role="user",
                content="test",
                tenant_id="tenant_b",
            )

    db_manager.close()


def test_tenant_isolated_state_store(tmp_path: Path):
    store = TenantIsolatedStateStore(
        base_dir=tmp_path / "tenants_state",
        model_cls=MockTenantItem,
        file_name="items.json",
    )

    with TenantContext("tenant_1"):
        store.set("item_a", MockTenantItem(id="a", name="Tenant 1 Asset"))
        assert store.get("item_a") is not None
        assert store.get("item_a").name == "Tenant 1 Asset"

    with TenantContext("tenant_2"):
        assert store.get("item_a") is None
        store.set("item_b", MockTenantItem(id="b", name="Tenant 2 Asset"))
        all_items = store.get_all()
        assert len(all_items) == 1
        assert "item_b" in all_items

    # Cross-tenant violation check
    with TenantContext("tenant_1"), pytest.raises(CrossTenantAccessViolationError):
        store.get("item_b", tenant_id="tenant_2")
