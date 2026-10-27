# ruff: noqa: PLR2004
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from amberclaw.api.auth import create_access_token
from amberclaw.api.main import app
from amberclaw.governance.tickets import Ticket, TicketStatus, tickets
from amberclaw.memory.session_db import SessionDB


@pytest.fixture
def auth_client():
    token = create_access_token(data={"sub": "testadmin", "role": "admin"})
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


def test_idempotency_header_replay(auth_client, tmp_path, monkeypatch):
    test_db = SessionDB(db_path=tmp_path / "idempotent_sessions.db")
    test_db.add_turn(session_id="idemp_sess_1", role="user", content="Hello test 1")
    monkeypatch.setattr("amberclaw.api.v1.memory.session_db", test_db)

    headers = {"X-Idempotency-Key": "unique-idemp-key-101"}

    # First request executes the purge/delete operation
    res1 = auth_client.delete("/api/v1/memory/sessions/idemp_sess_1", headers=headers)
    assert res1.status_code == status.HTTP_200_OK
    data1 = res1.json()
    assert data1["status"] == "success"
    assert data1["deleted_turns"] == 1
    assert "X-Idempotency-Replayed" not in res1.headers

    # Second request with same idempotency key replays cached response
    res2 = auth_client.delete("/api/v1/memory/sessions/idemp_sess_1", headers=headers)
    assert res2.status_code == status.HTTP_200_OK
    data2 = res2.json()
    assert data2 == data1
    assert res2.headers.get("X-Idempotency-Replayed") == "true"
    assert res2.headers.get("X-Cache") == "HIT"


def test_agents_pagination_and_ordering(auth_client):
    res_all = auth_client.get("/api/v1/agents?limit=100&offset=0&order_by=agent_id")
    assert res_all.status_code == status.HTTP_200_OK
    assert isinstance(res_all.json(), list)

    res_page = auth_client.get("/api/v1/agents?limit=1&offset=0")
    assert res_page.status_code == status.HTTP_200_OK
    assert len(res_page.json()) <= 1


def test_tickets_pagination(auth_client):
    # Populate test tickets in ticket store
    t1 = Ticket(
        id="tix_test_p1",
        requester_id="agent_1",
        description="Ticket 1 for pagination test",
        context={"cmd": "echo 1"},
    )
    t2 = Ticket(
        id="tix_test_p2",
        requester_id="agent_2",
        description="Ticket 2 for pagination test",
        context={"cmd": "echo 2"},
    )
    tickets._store.set(t1.id, t1)
    tickets._store.set(t2.id, t2)

    res_limit = auth_client.get("/api/v1/tickets/pending?limit=1&offset=0")
    assert res_limit.status_code == status.HTTP_200_OK
    data = res_limit.json()
    assert len(data) == 1

    # Cleanup
    tickets.resolve_ticket(t1.id, TicketStatus.APPROVED, "admin")
    tickets.resolve_ticket(t2.id, TicketStatus.REJECTED, "admin")


def test_memory_turns_pagination(auth_client, tmp_path, monkeypatch):
    test_db = SessionDB(db_path=tmp_path / "paginated_sessions.db")
    for i in range(5):
        test_db.add_turn(
            session_id="page_session_test",
            role="user" if i % 2 == 0 else "assistant",
            content=f"Turn message {i}",
        )
    monkeypatch.setattr("amberclaw.api.v1.memory.session_db", test_db)

    # Get page 1 (limit 2, offset 0)
    res_p1 = auth_client.get("/api/v1/memory/sessions/page_session_test/turns?limit=2&offset=0")
    assert res_p1.status_code == status.HTTP_200_OK
    turns_p1 = res_p1.json()
    assert len(turns_p1) == 2
    assert turns_p1[0]["turn_index"] == 0
    assert turns_p1[1]["turn_index"] == 1

    # Get page 2 (limit 2, offset 2)
    res_p2 = auth_client.get("/api/v1/memory/sessions/page_session_test/turns?limit=2&offset=2")
    assert res_p2.status_code == status.HTTP_200_OK
    turns_p2 = res_p2.json()
    assert len(turns_p2) == 2
    assert turns_p2[0]["turn_index"] == 2
    assert turns_p2[1]["turn_index"] == 3
