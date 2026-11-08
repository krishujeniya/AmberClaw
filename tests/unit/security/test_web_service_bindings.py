"""Dashboard data comes from injected local services, and chat uses AgentLoop's API."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from amberclaw.governance.tickets import TicketSystem
from amberclaw.security.audit import AuditEvent
from amberclaw.web.auth import WebAuthManager
from amberclaw.web.server import DashboardServices, UsageResponse, create_web_app


def authenticated_client(monkeypatch, services=None, base_url="http://testserver"):
    monkeypatch.setenv("WEB_ADMIN_USER", "operator")
    monkeypatch.setenv("WEB_ADMIN_PASS", "test-only-password")
    manager = WebAuthManager()
    client = TestClient(
        create_web_app(services=services, authentication=manager), base_url=base_url
    )
    response = client.post(
        "/api/web/login",
        json={"username": "operator", "password": "test-only-password"},
    )
    assert response.status_code == status.HTTP_200_OK
    return client, manager


def test_unconfigured_dashboard_reports_unavailable(monkeypatch):
    client, _manager = authenticated_client(monkeypatch)
    assert client.get("/api/sessions").json() == []
    assert client.get("/api/audit/logs").json() == []
    assert client.get("/api/metrics/usage").json()["estimated_spend_usd"] is None
    response = client.post("/api/chat/stream", json={"message": "hello"})
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@pytest.mark.asyncio
async def test_dashboard_reads_bound_services(monkeypatch, tmp_path):
    tickets = TicketSystem(data_dir=tmp_path)
    ticket = await tickets.create_ticket("operator", "Review isolated tool request")
    sessions = Mock()
    sessions.list_sessions.return_value = [
        {"key": "web:quality", "created_at": "2026-11-06T00:00:00Z"}
    ]
    usage = UsageResponse(total_tokens=17, estimated_spend_usd=0.01)
    event = AuditEvent(
        action="test.local_read",
        actor="operator",
        resource_id="quality",
        integrity_proof="verified-fixture-proof",
    )
    bound = DashboardServices(
        sessions=sessions,
        tickets=tickets,
        usage=lambda: usage,
        audit=lambda: [event],
        agent_count=lambda: 2,
    )
    client, _manager = authenticated_client(monkeypatch, bound)
    assert client.get("/api/sessions").json() == sessions.list_sessions.return_value
    sessions.list_sessions.assert_called_once()
    assert client.get("/api/governance/tickets").json() == [
        {"ticket_id": ticket.id, "action": ticket.description, "status": "pending"}
    ]
    assert client.get("/api/metrics/usage").json()["total_tokens"] == usage.total_tokens
    assert client.get("/api/audit/logs").json()[0]["hash"] == event.integrity_proof
    assert client.get("/api/dashboard/summary").json() == {
        "status": "unavailable",
        "active_agents": 2,
        "pending_tickets": 1,
    }


def test_chat_uses_canonical_direct_call_and_authenticated_session(monkeypatch):
    runtime = Mock()
    runtime.process_direct = AsyncMock(return_value="Actual runtime response")
    client, manager = authenticated_client(
        monkeypatch, DashboardServices(runtime=runtime)
    )
    response = client.post("/api/chat/stream", json={"message": "hello"})
    assert response.status_code == status.HTTP_200_OK
    assert response.text == "Actual runtime response"
    call = runtime.process_direct.call_args
    assert call.args == ("hello",)
    assert call.kwargs["channel"] == "web"
    token = client.cookies["amberclaw_web_session"]
    session = manager.verify_session(token)
    assert call.kwargs["session_key"] == f"web:{session.conversation_id}"
    assert call.kwargs["chat_id"] == session.conversation_id
    assert token not in call.kwargs["session_key"]
    assert callable(call.kwargs["on_token"])


def test_chat_streams_real_tokens_without_duplicate_final_text(monkeypatch):
    async def process(_content, **kwargs):
        await kwargs["on_token"]("real ")
        await kwargs["on_token"]("tokens")
        return "real tokens"

    runtime = Mock(process_direct=process)
    client, _manager = authenticated_client(
        monkeypatch, DashboardServices(runtime=runtime)
    )
    response = client.post("/api/chat/stream", json={"message": "hello"})
    assert response.text == "real tokens"


def test_runtime_failure_is_reported_honestly(monkeypatch):
    runtime = Mock(
        process_direct=AsyncMock(side_effect=RuntimeError("fixture failure"))
    )
    client, _manager = authenticated_client(
        monkeypatch, DashboardServices(runtime=runtime)
    )
    response = client.post("/api/chat/stream", json={"message": "hello"})
    assert "processing failed" in response.text
    assert "dispatch initialized" not in response.text


def test_expired_and_revoked_sessions_cannot_read(monkeypatch):
    client, manager = authenticated_client(monkeypatch)
    token = client.cookies["amberclaw_web_session"]
    session = manager.verify_session(token)
    session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert client.get("/api/sessions").status_code == status.HTTP_401_UNAUTHORIZED
    session = manager.create_session("operator")
    client.cookies.set("amberclaw_web_session", session.session_id)
    manager.revoke_session(session.session_id)
    assert client.get("/api/audit/logs").status_code == status.HTTP_401_UNAUTHORIZED


def test_cross_origin_mutations_are_denied(monkeypatch):
    client, _manager = authenticated_client(monkeypatch)
    for path, payload in [
        ("/api/web/logout", None),
        ("/api/chat/stream", {"message": "hello"}),
    ]:
        response = client.post(
            path, json=payload, headers={"Origin": "https://foreign.example"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


def test_https_login_cookie_is_secure(monkeypatch):
    client, _manager = authenticated_client(monkeypatch, base_url="https://testserver")
    response = client.post(
        "/api/web/login",
        json={"username": "operator", "password": "test-only-password"},
    )
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "secure" in cookie


def test_private_spa_is_not_indexable():
    response = TestClient(create_web_app()).get("/")
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert 'name="robots" content="noindex, nofollow"' in response.text
    assert "Zero-Trust Kernel Active</span>" not in response.text
    assert (
        "Task dispatched to agent loop. Processing in background." not in response.text
    )
    assert (
        "Execution completed: response delivered via secure channel."
        not in response.text
    )


def test_auth_cookie_is_not_forwarded_to_runtime_or_returned_in_body(monkeypatch):
    runtime = Mock(process_direct=AsyncMock(return_value="real result"))
    client, _manager = authenticated_client(
        monkeypatch, DashboardServices(runtime=runtime)
    )
    token = client.cookies["amberclaw_web_session"]
    response = client.post("/api/chat/stream", json={"message": "fixture"})
    assert response.status_code == status.HTTP_200_OK
    call = runtime.process_direct.call_args
    forwarded = str((call.args, call.kwargs["session_key"], call.kwargs["chat_id"]))
    assert token not in forwarded
    login = client.post(
        "/api/web/login",
        json={"username": "operator", "password": "test-only-password"},
    )
    assert client.cookies["amberclaw_web_session"] not in login.text
