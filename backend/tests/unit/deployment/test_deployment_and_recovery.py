# ruff: noqa: PLR2004
"""Unit tests for CL-018: Supported Deployment, Backup, Restore, and Disaster Recovery."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from amberclaw.deployment.manager import (
    DeploymentDrillObservation,
    DeploymentLifecycleManager,
    PersistentSessionStore,
    PrivateDeploymentConfig,
    SecretsRotationManager,
)
from amberclaw.runtime.durable import (
    DurableExecutionCoordinator,
    DurableRunStore,
    RunStatus,
    StepStatus,
)


def test_private_deployment_config_and_availability_denominator():
    """Verify private deployment configuration and 30-day pilot availability denominator."""
    config = PrivateDeploymentConfig(
        deployment_id="dep_test_01",
        storage_backend="sqlite",
        db_url="sqlite:///./data/amberclaw.db",
        rpo_target_minutes=15.0,
        rto_target_minutes=30.0,
        target_availability_pct=99.9,
        pilot_window_days=30,
        planned_maintenance_minutes=120.0,
    )
    metrics = config.calculate_availability_denominator()

    assert metrics["pilot_window_days"] == 30
    assert metrics["total_calendar_minutes"] == 43200
    assert metrics["planned_maintenance_minutes"] == 120.0
    assert metrics["net_operating_minutes"] == 43080
    assert metrics["target_availability_pct"] == 99.9
    # 43080 * 0.001 = 43.08 minutes maximum allowed unplanned downtime
    assert metrics["max_allowed_unplanned_downtime_minutes"] == 43.08
    assert metrics["rpo_target_minutes"] == 15.0
    assert metrics["rto_target_minutes"] == 30.0


def test_storage_backend_health_sqlite_and_postgresql(tmp_path):
    """Verify both supported storage backend paths: SQLite and PostgreSQL."""
    db_file = tmp_path / "test_store.db"
    sqlite_cfg = PrivateDeploymentConfig(
        storage_backend="sqlite",
        db_url=f"sqlite:///{db_file}",
    )
    mgr_sqlite = DeploymentLifecycleManager(sqlite_cfg)
    res_sqlite = mgr_sqlite.check_storage_backend()
    assert res_sqlite["backend"] == "sqlite"
    assert res_sqlite["healthy"] is True
    assert res_sqlite["journal_mode"] == "WAL"

    # PostgreSQL configuration path check
    pg_cfg = PrivateDeploymentConfig(
        storage_backend="postgresql",
        db_url="postgresql+asyncpg://amberclaw:secret@127.0.0.1:5432/amberclaw_prod",
    )
    mgr_pg = DeploymentLifecycleManager(pg_cfg)
    res_pg = mgr_pg.check_storage_backend()
    assert res_pg["backend"] == "postgresql"
    assert res_pg["configured_url_valid"] is True
    assert res_pg["healthy"] is True


def test_secrets_rotation_and_revocation(tmp_path):
    """Verify secrets rotation, version increments, and rejection of old revoked keys."""
    state_file = tmp_path / "secrets_vault.json"
    vault = SecretsRotationManager(state_file=state_file)

    # Register initial secret
    vault.register_secret("jwt_signing_key", "initial-super-secure-key-32-chars-long!")
    assert vault.verify_secret("jwt_signing_key", "initial-super-secure-key-32-chars-long!") is True
    assert vault.verify_secret("jwt_signing_key", "wrong-secret") is False

    # Rotate secret
    rotated = vault.rotate_secret(
        "jwt_signing_key",
        "new-rotated-super-secure-key-32-chars!",
        invalidate_old=True,
    )
    assert rotated.version == 2
    assert len(rotated.revoked_hashes) == 1

    # New secret succeeds
    assert vault.verify_secret("jwt_signing_key", "new-rotated-super-secure-key-32-chars!") is True
    # Old revoked secret must be explicitly rejected
    assert vault.verify_secret("jwt_signing_key", "initial-super-secure-key-32-chars-long!") is False

    # Reload from persistent state
    reloaded_vault = SecretsRotationManager(state_file=state_file)
    assert reloaded_vault.verify_secret("jwt_signing_key", "new-rotated-super-secure-key-32-chars!") is True
    assert reloaded_vault.verify_secret("jwt_signing_key", "initial-super-secure-key-32-chars-long!") is False


def test_persistent_session_invalidation_across_failover(tmp_path):
    """Verify revoked and expired sessions stay rejected after worker restart/failover."""
    session_db = tmp_path / "sessions.db"
    store1 = PersistentSessionStore(db_path=session_db)

    # 1. Active session
    s_active = store1.create_session(user_id="operator_alice", ttl_minutes=60)
    # 2. Revoked session
    s_revoked = store1.create_session(user_id="operator_bob", ttl_minutes=60)
    store1.revoke_session(s_revoked.session_id, reason="suspicious_activity")
    # 3. Expired session
    s_expired = store1.create_session(user_id="operator_carol", ttl_minutes=-10)

    # Immediate check
    assert store1.verify_session(s_active.session_id) is not None
    assert store1.verify_session(s_revoked.session_id) is None
    assert store1.verify_session(s_expired.session_id) is None

    # SIMULATE CRASH & FAILOVER: instantiate brand new session store instance pointing to same DB
    store2 = PersistentSessionStore(db_path=session_db)

    # After failover: active session survives
    v_active = store2.verify_session(s_active.session_id)
    assert v_active is not None
    assert v_active.user_id == "operator_alice"

    # After failover: revoked session STAYS REJECTED
    assert store2.verify_session(s_revoked.session_id) is None

    # After failover: expired session STAYS REJECTED
    assert store2.verify_session(s_expired.session_id) is None


def test_worker_restart_and_durable_run_recovery(tmp_path):
    """Verify worker restart recovers interrupted runs and preserves execution boundaries."""
    db_file = tmp_path / "durable_restart.db"
    store = DurableRunStore(db_path=db_file)

    run = store.create_run(
        tenant_id="tenant_dr",
        workflow_name="financial_ledger_sync",
        initial_input={"batch_id": "b100"},
    )
    # Create step in flight
    step = store.create_step(
        run_id=run.run_id,
        step_index=0,
        action_type="fetch_transactions",
        idempotency_key="ik_b100_step0",
    )
    store.mark_step_in_flight(step.step_id)

    cfg = PrivateDeploymentConfig(
        storage_backend="sqlite",
        db_url=f"sqlite:///{db_file}",
    )
    mgr = DeploymentLifecycleManager(cfg)

    # Restart worker and recover
    recovered = mgr.restart_worker_and_recover_runs(store)
    assert len(recovered) >= 1
    rec = next(r for r in recovered if r.run_id == run.run_id)
    assert rec.run_id == run.run_id
    assert rec.can_auto_resume is True
    assert rec.resume_step_index == 0


def test_disaster_recovery_drill_observing_rpo_and_rto(tmp_path):
    """Execute complete DR drill verifying RPO <= 15m and RTO <= 30m."""
    data_dir = tmp_path / "data"
    backup_dir = tmp_path / "backups"
    data_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)

    cfg = PrivateDeploymentConfig(
        rpo_target_minutes=15.0,
        rto_target_minutes=30.0,
    )
    mgr = DeploymentLifecycleManager(cfg)

    observation = mgr.exercise_dr_drill(data_dir=data_dir, backup_dir=backup_dir)

    assert observation.rpo_target_met is True
    assert observation.rto_target_met is True
    assert observation.recovery_integrity_passed is True
    # RPO and RTO should be seconds in local test, well under the 15m / 30m target ceilings
    assert observation.observed_rpo_seconds < 900.0  # 15 minutes
    assert observation.observed_rto_seconds < 1800.0  # 30 minutes
