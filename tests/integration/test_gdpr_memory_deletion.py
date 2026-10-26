# ruff: noqa: PLR2004
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from amberclaw.api.auth import create_access_token
from amberclaw.api.main import app
from amberclaw.memory.session_db import SessionDB


@pytest.fixture
def unauth_client():
    return TestClient(app)


@pytest.fixture
def auth_client():
    token = create_access_token(data={"sub": "admin", "role": "admin"})
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


@pytest.fixture
def session_db(tmp_path):
    db_file = tmp_path / "test_sessions.db"
    return SessionDB(db_path=db_file)


def test_unauthenticated_gdpr_memory_deletion(unauth_client):
    res_sess = unauth_client.delete("/api/v1/memory/sessions/test_sess_123")
    assert res_sess.status_code == status.HTTP_401_UNAUTHORIZED

    res_purge = unauth_client.delete("/api/v1/memory/purge")
    assert res_purge.status_code == status.HTTP_401_UNAUTHORIZED

    res_export = unauth_client.get("/api/v1/memory/export")
    assert res_export.status_code == status.HTTP_401_UNAUTHORIZED


def test_authenticated_gdpr_memory_deletion(auth_client, monkeypatch, tmp_path):
    test_db = SessionDB(db_path=tmp_path / "gdpr_sessions.db")
    test_db.add_turn(
        session_id="gdpr_session_1",
        role="user",
        content="Sensitive personal data for GDPR test",
        user_id="user_123",
    )
    assert len(test_db.get_turns("gdpr_session_1")) == 1

    monkeypatch.setattr("amberclaw.api.v1.memory.session_db", test_db)

    # Delete specific session memory
    del_res = auth_client.delete("/api/v1/memory/sessions/gdpr_session_1")
    assert del_res.status_code == status.HTTP_200_OK
    data = del_res.json()
    assert data["status"] == "success"
    assert data["deleted_turns"] == 1
    assert len(test_db.get_turns("gdpr_session_1")) == 0

    # Right-to-be-forgotten full memory purge
    test_db.add_turn(session_id="purge_sess", role="user", content="Data to purge")

    # Export test prior to purge
    export_res = auth_client.get("/api/v1/memory/export?session_id=purge_sess")
    assert export_res.status_code == status.HTTP_200_OK
    exp_data = export_res.json()
    assert exp_data["schema_version"] == "2026.1.0"
    assert exp_data["total_turns"] == 1
    assert exp_data["session_id"] == "purge_sess"
    assert "checksum_sha256" in exp_data
    assert len(exp_data["checksum_sha256"]) == 64

    purge_res = auth_client.delete("/api/v1/memory/purge")
    assert purge_res.status_code == status.HTTP_200_OK
    purge_data = purge_res.json()
    assert purge_data["status"] == "success"
    assert purge_data["deleted_turns"] == 1
    assert len(test_db.get_turns("purge_sess")) == 0
