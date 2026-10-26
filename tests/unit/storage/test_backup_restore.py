# ruff: noqa: PLR2004
"""Unit tests for AmberClaw Disaster Recovery, Backup, and Restoration Engine."""

import io
import json
import sqlite3
import tarfile
from pathlib import Path

import pytest

from amberclaw.storage.backup import (
    BackupSecurityError,
    DisasterRecoveryManager,
)


@pytest.fixture
def populated_env(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True)
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True)

    # 1. Create SQLite DB with WAL mode
    db_file = data_dir / "sessions.db"
    with sqlite3.connect(str(db_file)) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(
            "CREATE TABLE session_turns (id INTEGER PRIMARY KEY, content TEXT);"
        )
        conn.execute(
            "INSERT INTO session_turns (content) VALUES ('turn 1'), ('turn 2');"
        )
        conn.commit()

    # 2. Create Tenant SQLite DB
    tenant_db_file = data_dir / "tenants" / "org_alpha" / "sessions.db"
    tenant_db_file.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(tenant_db_file)) as conn:
        conn.execute(
            "CREATE TABLE session_turns (id INTEGER PRIMARY KEY, content TEXT);"
        )
        conn.execute("INSERT INTO session_turns (content) VALUES ('tenant turn A');")
        conn.commit()

    # 3. Create JSON state file
    state_file = data_dir / "agents.json"
    state_file.write_text(
        json.dumps({"agent_1": {"name": "TestAgent"}}), encoding="utf-8"
    )

    # 4. Create config file
    cfg_file = config_dir / "settings.yaml"
    cfg_file.write_text("system:\n  name: AmberClaw\n", encoding="utf-8")

    # 5. Create audit log
    log_file = logs_dir / "audit.jsonl"
    log_file.write_text('{"event": "system.init", "status": "ok"}\n', encoding="utf-8")

    return {
        "data_dir": data_dir,
        "backup_dir": backup_dir,
        "config_dir": config_dir,
        "logs_dir": logs_dir,
        "tmp_path": tmp_path,
    }


def test_create_and_restore_backup(populated_env):
    mgr = DisasterRecoveryManager(
        data_dir=populated_env["data_dir"],
        backup_dir=populated_env["backup_dir"],
        config_dir=populated_env["config_dir"],
        logs_dir=populated_env["logs_dir"],
    )

    # 1. Create backup
    archive = mgr.create_backup(name="test_snap_01")
    assert archive.exists()
    assert archive.name == "test_snap_01.tar.gz"

    # Verify manifest sidecar
    manifests = mgr.list_backups()
    assert len(manifests) == 1
    assert manifests[0]["backup_id"] == "test_snap_01"
    assert manifests[0]["total_files"] >= 5

    # 2. Restore into a new isolated clean directory
    restore_target = populated_env["tmp_path"] / "restored_env"
    restored_manifest = mgr.restore_backup(
        archive_path=archive, target_dir=restore_target
    )
    assert restored_manifest.backup_id == "test_snap_01"

    # Verify restored SQLite DB
    restored_db = restore_target / "data" / "sessions.db"
    assert restored_db.exists()
    with sqlite3.connect(str(restored_db)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM session_turns;")
        assert cursor.fetchone()[0] == 2

    # Verify tenant DB
    restored_tenant_db = (
        restore_target / "data" / "tenants" / "org_alpha" / "sessions.db"
    )
    assert restored_tenant_db.exists()
    with sqlite3.connect(str(restored_tenant_db)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM session_turns;")
        assert cursor.fetchone()[0] == 1

    # Verify JSON state and config
    restored_json = restore_target / "data" / "agents.json"
    assert restored_json.exists()
    assert "agent_1" in json.loads(restored_json.read_text(encoding="utf-8"))

    # Overwrite protection check (should fail without force)
    with pytest.raises(FileExistsError):
        mgr.restore_backup(archive_path=archive, target_dir=restore_target, force=False)

    # Overwrite check with force
    mgr.restore_backup(archive_path=archive, target_dir=restore_target, force=True)


def test_path_traversal_zip_slip_rejection(tmp_path: Path):
    malicious_archive = tmp_path / "malicious.tar.gz"
    with tarfile.open(malicious_archive, "w:gz") as tar:
        # Add normal manifest
        manifest_data = json.dumps(
            {
                "backup_id": "evil_bak",
                "created_at": "2026-10-26T00:00:00",
                "amberclaw_version": "2026.0.1",
                "total_files": 1,
                "total_size_bytes": 10,
                "files": [
                    {
                        "relative_path": "../escape.txt",
                        "size_bytes": 10,
                        "sha256": "abc",
                    }
                ],
            }
        ).encode("utf-8")
        ti = tarfile.TarInfo(name="manifest.json")
        ti.size = len(manifest_data)
        tar.addfile(ti, io.BytesIO(manifest_data))

        # Add traversal file
        evil_data = b"malicious payload"
        evil_ti = tarfile.TarInfo(name="../escape.txt")
        evil_ti.size = len(evil_data)
        tar.addfile(evil_ti, io.BytesIO(evil_data))

    mgr = DisasterRecoveryManager(backup_dir=tmp_path)
    with pytest.raises(BackupSecurityError, match="path traversal"):
        mgr.restore_backup(malicious_archive, target_dir=tmp_path / "safe_zone")


def test_automated_disaster_recovery_drill(populated_env):
    mgr = DisasterRecoveryManager(
        data_dir=populated_env["data_dir"],
        backup_dir=populated_env["backup_dir"],
        config_dir=populated_env["config_dir"],
        logs_dir=populated_env["logs_dir"],
    )

    drill_res = mgr.run_dr_drill()
    assert drill_res.success is True
    assert drill_res.databases_checked >= 2
    assert drill_res.records_checked >= 3
    assert drill_res.duration_seconds > 0.0
    assert drill_res.error is None
